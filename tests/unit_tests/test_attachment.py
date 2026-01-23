"""Tests for attachment functionality."""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from platzky.attachment import (
    DEFAULT_MAX_ATTACHMENT_SIZE,
    AttachmentProtocol,
    AttachmentSizeError,
    BlockedExtensionError,
    ContentMismatchError,
    ExtensionNotAllowedError,
    InvalidMimeTypeError,
    create_attachment_class,
)
from platzky.config import (
    _DEFAULT_ALLOWED_MIME_TYPES,  # pyright: ignore[reportPrivateUsage]
    AttachmentConfig,
    Config,
)
from platzky.db.json_db import db_from_config
from platzky.engine import Engine
from tests.unit_tests.fake_app import test_app  # noqa: F401  # pyright: ignore[reportUnusedImport]


@pytest.fixture
def default_attachment_class():
    """Create an Attachment class with default config and common extensions."""
    return create_attachment_class(
        AttachmentConfig(
            allowed_extensions=frozenset({"pdf", "png", "jpg", "gif", "zip", "bin"}),
        )
    )


@pytest.fixture
def no_validation_attachment_class():
    """Create an Attachment class with content validation disabled."""
    return create_attachment_class(
        AttachmentConfig(
            validate_content=False,
            allowed_extensions=frozenset({"pdf", "png", "zip", "docx", "xlsx", "txt", "bin"}),
        )
    )


@pytest.fixture
def text_allowed_attachment_class():
    """Create an Attachment class with text types allowed."""
    return create_attachment_class(
        AttachmentConfig(
            allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
            validate_content=False,
            allowed_extensions=frozenset({"txt", "bin", "pdf", "png"}),
        )
    )


class TestAttachmentBasics:
    """Core attachment creation and validation tests."""

    def test_valid_attachment(self, default_attachment_class: type):
        """Test creating a valid attachment."""
        attachment = default_attachment_class(
            filename="test.pdf",
            content=b"%PDF-1.7 content here",
            mime_type="application/pdf",
        )
        assert attachment.filename == "test.pdf"
        assert attachment.mime_type == "application/pdf"
        assert isinstance(attachment, AttachmentProtocol)

    def test_empty_filename_raises_error(self, text_allowed_attachment_class: type):
        """Test that empty filename raises ValueError."""
        with pytest.raises(ValueError, match="filename cannot be empty"):
            text_allowed_attachment_class(filename="", content=b"content", mime_type="text/plain")

    @pytest.mark.parametrize("filename", [".", "..", "/", "//"])
    def test_invalid_filenames_rejected(self, filename: str, text_allowed_attachment_class: type):
        """Test that directory traversal filenames are rejected."""
        with pytest.raises(ValueError, match="filename cannot be empty"):
            text_allowed_attachment_class(filename=filename, content=b"c", mime_type="text/plain")

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("../../../etc/secret.txt", "secret.txt"),
            ("/etc/config.txt", "config.txt"),
            ("C:\\Users\\test\\file.txt", "file.txt"),
        ],
    )
    def test_path_sanitization(
        self, filename: str, expected: str, caplog: pytest.LogCaptureFixture,
        text_allowed_attachment_class: type,
    ):
        """Test that path components are stripped from filename."""
        with caplog.at_level(logging.WARNING):
            attachment = text_allowed_attachment_class(
                filename=filename, content=b"content", mime_type="text/plain"
            )
        assert attachment.filename == expected

    def test_size_validation(self, text_allowed_attachment_class: type):
        """Test attachment size limits."""
        Attachment = text_allowed_attachment_class
        # Exactly at max size - should work
        attachment = Attachment(
            filename="max.bin",
            content=b"x" * DEFAULT_MAX_ATTACHMENT_SIZE,
            mime_type="text/plain",
        )
        assert len(attachment.content) == DEFAULT_MAX_ATTACHMENT_SIZE

        # Over max size - should fail
        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment(
                filename="large.bin",
                content=b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1),
                mime_type="text/plain",
            )

    def test_custom_max_size(self):
        """Test that custom max_size is respected."""
        Attachment = create_attachment_class(
            AttachmentConfig(
                max_size=100,
                allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
                validate_content=False,
                allowed_extensions=frozenset({"txt"}),
            )
        )
        # At limit - works
        assert len(Attachment("s.txt", b"x" * 100, "text/plain").content) == 100
        # Over limit - fails
        with pytest.raises(AttachmentSizeError):
            Attachment("big.txt", b"x" * 101, "text/plain")

    def test_mime_type_validation(self, default_attachment_class: type):
        """Test MIME type validation."""
        Attachment = default_attachment_class
        # Invalid format
        with pytest.raises(InvalidMimeTypeError, match="Invalid MIME type format") as exc_info:
            Attachment(filename="file.pdf", content=b"content", mime_type="invalid")
        assert exc_info.value.invalid_format is True

        # Not in allowlist
        with pytest.raises(InvalidMimeTypeError, match="is not allowed") as exc_info:
            Attachment(
                filename="file.bin", content=b"content", mime_type="application/x-executable"
            )
        assert exc_info.value.invalid_format is False


class TestAttachmentFactoryMethods:
    """Tests for from_bytes() and from_file() factory methods."""

    def test_from_bytes(self, text_allowed_attachment_class: type):
        """Test from_bytes creates valid attachment and validates size."""
        Attachment = text_allowed_attachment_class
        attachment = Attachment.from_bytes(
            content=b"content", filename="test.txt", mime_type="text/plain"
        )
        assert attachment.filename == "test.txt"

        # Size validation
        with pytest.raises(AttachmentSizeError):
            Attachment.from_bytes(
                content=b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1),
                filename="large.bin",
                mime_type="text/plain",
            )

    def test_from_file(self, tmp_path: Path, text_allowed_attachment_class: type):
        """Test from_file creates valid attachment."""
        Attachment = text_allowed_attachment_class
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello, World!")

        attachment = Attachment.from_file(file_path=test_file, mime_type="text/plain")
        assert attachment.filename == "test.txt"
        assert attachment.content == b"Hello, World!"

    def test_from_file_with_custom_filename(
        self, tmp_path: Path, text_allowed_attachment_class: type
    ):
        """Test from_file with custom filename override."""
        Attachment = text_allowed_attachment_class
        test_file = tmp_path / "original.txt"
        test_file.write_bytes(b"content")

        attachment = Attachment.from_file(
            file_path=test_file, filename="custom.txt", mime_type="text/plain"
        )
        assert attachment.filename == "custom.txt"

    def test_from_file_guesses_mime_type(
        self, tmp_path: Path, no_validation_attachment_class: type
    ):
        """Test that from_file guesses MIME type from filename."""
        Attachment = no_validation_attachment_class
        pdf_file = tmp_path / "document.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf")

        attachment = Attachment.from_file(file_path=pdf_file)
        assert attachment.mime_type == "application/pdf"

    def test_from_file_toctou_protection(self, tmp_path: Path):
        """Test that from_file catches files that grow between stat and read."""
        Attachment = create_attachment_class(
            AttachmentConfig(
                max_size=100,
                allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
                validate_content=False,
                allowed_extensions=frozenset({"txt"}),
            )
        )
        test_file = tmp_path / "growing.txt"
        test_file.write_bytes(b"x" * 50)  # Small enough to pass stat check

        # Mock to return more data than stat reported
        mock_file = MagicMock()
        mock_file.read.return_value = b"x" * 101
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)

        with patch.object(Path, "open", return_value=mock_file):
            with pytest.raises(AttachmentSizeError):
                Attachment.from_file(file_path=test_file, mime_type="text/plain")

    def test_max_size_override(self, tmp_path: Path):
        """Test max_size_override for both from_bytes and from_file."""
        Attachment = create_attachment_class(
            AttachmentConfig(
                max_size=100,
                allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
                validate_content=False,
                allowed_extensions=frozenset({"txt"}),
            )
        )

        # from_bytes: override allows larger content
        attachment = Attachment.from_bytes(
            content=b"x" * 200, filename="large.txt", mime_type="text/plain",
            max_size_override=500,
        )
        assert len(attachment.content) == 200

        # from_bytes: override still enforced
        with pytest.raises(AttachmentSizeError):
            Attachment.from_bytes(
                content=b"x" * 600, filename="huge.txt", mime_type="text/plain",
                max_size_override=500,
            )

        # from_file: same behavior
        large_file = tmp_path / "large.txt"
        large_file.write_bytes(b"x" * 200)
        attachment = Attachment.from_file(
            file_path=large_file, mime_type="text/plain", max_size_override=500
        )
        assert len(attachment.content) == 200


class TestEngineAttachment:
    """Tests for Engine.Attachment integration."""

    def test_engine_exposes_attachment_class(self):
        """Test that Engine exposes a configured Attachment class."""
        config_data = {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {"TYPE": "json", "DATA": {"site_content": {"pages": []}}},
            "ATTACHMENT": {
                "allowed_mime_types": list(_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"}),
                "validate_content": False,
                "max_size": 1000,
                "allowed_extensions": ["txt"],
            },
        }
        config = Config.model_validate(config_data)
        db = db_from_config(config.db)  # type: ignore[arg-type]
        engine = Engine(config, db, "test")

        # Can create attachments
        attachment = engine.Attachment("test.txt", b"hello", "text/plain")
        assert attachment.filename == "test.txt"

        # Respects configured max_size
        with pytest.raises(AttachmentSizeError):
            engine.Attachment("test.txt", b"x" * 1001, "text/plain")


class TestNotifierWithAttachments:
    """Tests for notifier functionality with attachments."""

    @pytest.fixture
    def text_allowed_test_app(self):
        """Create an Engine with text types allowed for attachments."""
        config_data = {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {"TYPE": "json", "DATA": {"site_content": {"pages": []}}},
            "ATTACHMENT": {
                "allowed_mime_types": list(_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"}),
                "validate_content": False,
                "allowed_extensions": ["txt"],
            },
        }
        config = Config.model_validate(config_data)
        db = db_from_config(config.db)  # type: ignore[arg-type]
        return Engine(config, db, "test")

    def test_notifiers_receive_attachments(self, text_allowed_test_app: Engine):
        """Test that notifiers correctly receive messages and attachments."""
        simple_messages: list[str] = []
        attachment_data: list[list[Any] | None] = []

        def simple_notifier(message: str) -> None:
            simple_messages.append(message)

        def notifier_with_attachments(
            message: str, attachments: list[Any] | None = None  # noqa: ARG001
        ) -> None:
            attachment_data.append(attachments)

        attachment = text_allowed_test_app.Attachment("test.txt", b"hello", "text/plain")
        text_allowed_test_app.add_notifier(simple_notifier)
        text_allowed_test_app.add_notifier_with_attachments(notifier_with_attachments)
        text_allowed_test_app.notify("test message", attachments=[attachment])

        assert simple_messages == ["test message"]
        assert attachment_data[0] is not None
        assert attachment_data[0][0].filename == "test.txt"


class TestMagicByteValidation:
    """Tests for magic byte content validation."""

    @pytest.mark.parametrize(
        ("mime_type", "magic_bytes"),
        [
            ("image/png", b"\x89PNG\r\n\x1a\n"),
            ("image/jpeg", b"\xff\xd8\xff"),
            ("application/pdf", b"%PDF"),
            ("application/zip", b"PK\x03\x04"),
        ],
    )
    def test_valid_magic_bytes(
        self, mime_type: str, magic_bytes: bytes, default_attachment_class: type
    ):
        """Test MIME types with correct magic bytes are accepted."""
        content = magic_bytes + b"rest of file data"
        attachment = default_attachment_class(
            filename="file.bin", content=content, mime_type=mime_type
        )
        assert attachment.content == content

    @pytest.mark.parametrize("mime_type", ["image/png", "image/jpeg", "application/pdf"])
    def test_invalid_content_raises_error(self, mime_type: str, default_attachment_class: type):
        """Test MIME types with invalid content are rejected."""
        with pytest.raises(ContentMismatchError):
            default_attachment_class(
                filename="file.bin",
                content=b"INVALID CONTENT",
                mime_type=mime_type,
            )

    def test_mismatched_content_type_raises_error(self, default_attachment_class: type):
        """Test that content recognized as different type raises error."""
        # Valid PNG magic bytes but declared as PDF
        png_content = b"\x89PNG\r\n\x1a\n" + b"fake png data"
        with pytest.raises(ContentMismatchError, match="Detected types:"):
            default_attachment_class(
                filename="fake.pdf", content=png_content, mime_type="application/pdf"
            )

    def test_validation_bypass_options(self):
        """Test various ways to bypass content validation."""
        # allow_unrecognized_content=True
        Attachment1 = create_attachment_class(
            AttachmentConfig(
                allowed_mime_types=frozenset({"application/octet-stream"}),
                allow_unrecognized_content=True,
                allowed_extensions=frozenset({"bin"}),
            )
        )
        assert Attachment1("f.bin", b"random xyz", "application/octet-stream").content is not None

        # validate_content=False
        Attachment2 = create_attachment_class(
            AttachmentConfig(validate_content=False, allowed_extensions=frozenset({"png"}))
        )
        assert Attachment2("i.png", b"invalid", "image/png").content == b"invalid"

        # Empty content skips validation
        Attachment3 = create_attachment_class(
            AttachmentConfig(allowed_extensions=frozenset({"png"}))
        )
        assert Attachment3("empty.png", b"", "image/png").content == b""


class TestMimeTypeRestrictions:
    """Tests for MIME type restrictions."""

    @pytest.mark.parametrize(
        "mime_type",
        ["text/plain", "text/html", "application/json", "image/svg+xml"],
    )
    def test_text_types_not_allowed_by_default(
        self, mime_type: str, default_attachment_class: type
    ):
        """Test that text/* and related types are rejected by default."""
        with pytest.raises(ValueError, match="is not allowed"):
            default_attachment_class(
                filename="test.bin", content=b"content", mime_type=mime_type
            )

    def test_text_types_can_be_explicitly_allowed(self):
        """Test that text types can be explicitly allowed."""
        Attachment = create_attachment_class(
            AttachmentConfig(
                allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
                validate_content=False,
                allowed_extensions=frozenset({"txt"}),
            )
        )
        attachment = Attachment("test.txt", b"Hello", "text/plain")
        assert attachment.mime_type == "text/plain"


class TestExtensionValidation:
    """Tests for file extension validation (blocking and allowing)."""

    @pytest.mark.parametrize("extension", ["exe", "bat", "ps1", "sh", "py", "jar"])
    def test_blocked_extensions_rejected(self, extension: str, default_attachment_class: type):
        """Test that dangerous extensions are rejected."""
        with pytest.raises(BlockedExtensionError, match="blocked extension"):
            default_attachment_class(
                filename=f"malware.{extension}",
                content=b"content",
                mime_type="application/pdf",
            )

    def test_blocked_extension_case_insensitive(self, default_attachment_class: type):
        """Test that extension blocking is case insensitive."""
        for ext in ["EXE", "Exe", "exe"]:
            with pytest.raises(BlockedExtensionError):
                default_attachment_class(
                    filename=f"file.{ext}", content=b"c", mime_type="application/pdf"
                )

    def test_blocked_extension_checked_before_mime_type(self, default_attachment_class: type):
        """Test that extension is validated before MIME type."""
        with pytest.raises(BlockedExtensionError):
            default_attachment_class(filename="malware.exe", content=b"c", mime_type="invalid")

    def test_blocked_extension_error_attributes(self, default_attachment_class: type):
        """Test BlockedExtensionError attributes."""
        with pytest.raises(BlockedExtensionError) as exc_info:
            default_attachment_class(
                filename="virus.exe", content=b"c", mime_type="application/pdf"
            )
        assert exc_info.value.filename == "virus.exe"
        assert exc_info.value.extension == "exe"

    def test_blocked_takes_precedence_over_allowed(self):
        """Test that blocked_extensions takes precedence over allowed_extensions."""
        Attachment = create_attachment_class(
            AttachmentConfig(
                validate_content=False,
                blocked_extensions=frozenset({"exe"}),
                allowed_extensions=frozenset({"exe", "pdf"}),
            )
        )
        with pytest.raises(BlockedExtensionError):
            Attachment("app.exe", b"content", "application/pdf")
        # pdf should work
        assert Attachment("doc.pdf", b"%PDF", "application/pdf").filename == "doc.pdf"

    @pytest.mark.parametrize(
        "filename", ["document.pdf", "image.png", "archive.zip", "report.docx"]
    )
    def test_safe_extensions_allowed(self, filename: str, no_validation_attachment_class: type):
        """Test that safe extensions are allowed."""
        mime_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".zip": "application/zip",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        ext = "." + filename.rsplit(".", 1)[-1]
        attachment = no_validation_attachment_class(
            filename=filename, content=b"c", mime_type=mime_types[ext]
        )
        assert attachment.filename == filename


class TestExtensionAllowList:
    """Tests for extension allow-list functionality."""

    def test_allowed_extensions_none_or_empty_blocks_all(self):
        """Test that None or empty allowed_extensions blocks all extensions."""
        for allowed in [None, frozenset()]:
            Attachment = create_attachment_class(
                AttachmentConfig(validate_content=False, allowed_extensions=allowed)
            )
            with pytest.raises(ExtensionNotAllowedError):
                Attachment("file.pdf", b"content", "application/pdf")

    def test_allowed_extensions_filtering(self):
        """Test that only listed extensions are allowed."""
        Attachment = create_attachment_class(
            AttachmentConfig(validate_content=False, allowed_extensions=frozenset({"pdf", "png"}))
        )
        # Allowed
        assert Attachment("doc.pdf", b"%PDF", "application/pdf").filename == "doc.pdf"
        # Not allowed
        with pytest.raises(ExtensionNotAllowedError, match="not in the allowed"):
            Attachment("image.gif", b"content", "image/gif")

    def test_no_extension_blocked_when_allow_list_set(self):
        """Test that files without extension are blocked when allow-list is set."""
        Attachment = create_attachment_class(
            AttachmentConfig(validate_content=False, allowed_extensions=frozenset({"pdf"}))
        )
        with pytest.raises(ExtensionNotAllowedError, match="no file extension"):
            Attachment("README", b"content", "application/pdf")

    def test_extension_not_allowed_error_attributes(self):
        """Test ExtensionNotAllowedError attributes."""
        Attachment = create_attachment_class(
            AttachmentConfig(validate_content=False, allowed_extensions=frozenset({"pdf"}))
        )
        # With extension
        with pytest.raises(ExtensionNotAllowedError) as exc_info:
            Attachment("image.png", b"content", "image/png")
        assert exc_info.value.filename == "image.png"
        assert exc_info.value.extension == "png"

        # Without extension
        with pytest.raises(ExtensionNotAllowedError) as exc_info:
            Attachment("README", b"content", "application/pdf")
        assert exc_info.value.extension is None

    def test_allowed_extensions_case_insensitive(self):
        """Test that extension matching is case-insensitive."""
        Attachment = create_attachment_class(
            AttachmentConfig(validate_content=False, allowed_extensions=frozenset({"pdf"}))
        )
        assert Attachment("document.PDF", b"%PDF", "application/pdf").filename == "document.PDF"

    def test_default_allowed_extensions_work(self):
        """Test that the default allowed_extensions allow common file types."""
        Attachment = create_attachment_class(AttachmentConfig(validate_content=False))

        # Common extensions should work
        assert Attachment("photo.png", b"c", "image/png").filename == "photo.png"
        assert Attachment("doc.pdf", b"c", "application/pdf").filename == "doc.pdf"
        assert Attachment("data.zip", b"c", "application/zip").filename == "data.zip"

        # Extensions not in default list should be rejected
        with pytest.raises(ExtensionNotAllowedError):
            Attachment("code.json", b"{}", "application/json")
