import logging
from pathlib import Path
from typing import Any

import pytest

from platzky.attachment import (
    DEFAULT_MAX_ATTACHMENT_SIZE,
    AttachmentProtocol,
    AttachmentSizeError,
    BlockedExtensionError,
    ContentMismatchError,
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
    """Create an Attachment class with default configuration."""
    return create_attachment_class(AttachmentConfig())


@pytest.fixture
def no_validation_attachment_class():
    """Create an Attachment class with content validation disabled."""
    return create_attachment_class(
        AttachmentConfig(
            validate_content=False,
        )
    )


@pytest.fixture
def text_allowed_attachment_class():
    """Create an Attachment class with text types explicitly allowed."""
    return create_attachment_class(
        AttachmentConfig(
            allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain", "text/html"},
            validate_content=False,
        )
    )


class TestAttachment:
    """Tests for the Attachment dataclass validation."""

    def test_valid_attachment(self, default_attachment_class: type):
        """Test creating a valid attachment."""
        Attachment = default_attachment_class
        attachment = Attachment(
            filename="test.pdf",
            content=b"%PDF-1.7 content here",
            mime_type="application/pdf",
        )
        assert attachment.filename == "test.pdf"
        assert attachment.mime_type == "application/pdf"

    def test_empty_filename_raises_error(self, text_allowed_attachment_class: type):
        """Test that empty filename raises ValueError."""
        Attachment = text_allowed_attachment_class
        with pytest.raises(ValueError, match="filename cannot be empty"):
            Attachment(filename="", content=b"content", mime_type="text/plain")

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("../../../etc/passwd", "passwd"),
            ("/etc/passwd", "passwd"),
            ("C:\\Users\\test\\file.txt", "file.txt"),
        ],
    )
    def test_path_sanitization(
        self,
        filename: str,
        expected: str,
        caplog: pytest.LogCaptureFixture,
        text_allowed_attachment_class: type,
    ):
        """Test that path components are stripped from filename."""
        Attachment = text_allowed_attachment_class
        with caplog.at_level(logging.WARNING):
            attachment = Attachment(filename=filename, content=b"content", mime_type="text/plain")
        assert attachment.filename == expected

    def test_oversized_attachment_raises_error(self, text_allowed_attachment_class: type):
        """Test that attachment exceeding max size raises AttachmentSizeError."""
        Attachment = text_allowed_attachment_class
        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment(
                filename="large.bin",
                content=b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1),
                mime_type="text/plain",
            )

    def test_max_size_attachment_allowed(self, text_allowed_attachment_class: type):
        """Test that attachment at exactly max size is allowed."""
        Attachment = text_allowed_attachment_class
        attachment = Attachment(
            filename="max.bin",
            content=b"x" * DEFAULT_MAX_ATTACHMENT_SIZE,
            mime_type="text/plain",
        )
        assert len(attachment.content) == DEFAULT_MAX_ATTACHMENT_SIZE

    def test_invalid_mime_type_format_raises_error(self, default_attachment_class: type):
        """Test that invalid MIME type format raises ValueError."""
        Attachment = default_attachment_class
        with pytest.raises(ValueError, match="Invalid MIME type format"):
            Attachment(filename="file.txt", content=b"content", mime_type="invalid")

    def test_disallowed_mime_type_raises_error(self, default_attachment_class: type):
        """Test that MIME type not in allowlist raises ValueError."""
        Attachment = default_attachment_class
        with pytest.raises(ValueError, match="is not allowed"):
            Attachment(
                filename="file.bin", content=b"content", mime_type="application/x-executable"
            )

    def test_custom_allowed_mime_types_extends_default(self):
        """Test that custom allowed_mime_types extends the default list."""
        custom_type = "application/x-custom"
        Attachment = create_attachment_class(
            AttachmentConfig(
                allowed_mime_types=frozenset({custom_type}),
                allow_unrecognized_content=True,
            )
        )
        attachment = Attachment(
            filename="custom.file",
            content=b"content",
            mime_type=custom_type,
        )
        assert attachment.mime_type == custom_type

    def test_custom_max_size(self):
        """Test that custom max_size is respected."""
        small_max = 100
        Attachment = create_attachment_class(
            AttachmentConfig(
                max_size=small_max,
                allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
                validate_content=False,
            )
        )
        # Should work at exactly max size
        attachment = Attachment(
            filename="small.txt",
            content=b"x" * small_max,
            mime_type="text/plain",
        )
        assert len(attachment.content) == small_max

        # Should fail above max size
        with pytest.raises(AttachmentSizeError):
            Attachment(
                filename="too_big.txt",
                content=b"x" * (small_max + 1),
                mime_type="text/plain",
            )


class TestAttachmentFromBytes:
    """Tests for the Attachment.from_bytes() factory method."""

    def test_from_bytes_creates_valid_attachment(self, text_allowed_attachment_class: type):
        """Test that from_bytes creates a valid attachment."""
        Attachment = text_allowed_attachment_class
        attachment = Attachment.from_bytes(
            content=b"content", filename="test.txt", mime_type="text/plain"
        )
        assert attachment.filename == "test.txt"

    def test_from_bytes_validates_size_before_creation(self, text_allowed_attachment_class: type):
        """Test that from_bytes validates size before object creation."""
        Attachment = text_allowed_attachment_class
        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_bytes(
                content=b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1),
                filename="large.bin",
                mime_type="text/plain",
            )


class TestAttachmentFromFile:
    """Tests for the Attachment.from_file() factory method."""

    def test_from_file_creates_valid_attachment(
        self, tmp_path: Path, text_allowed_attachment_class: type
    ):
        """Test that from_file creates a valid attachment."""
        Attachment = text_allowed_attachment_class
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello, World!")

        attachment = Attachment.from_file(file_path=test_file, mime_type="text/plain")
        assert attachment.filename == "test.txt"
        assert attachment.content == b"Hello, World!"

    def test_from_file_validates_size(self, tmp_path: Path, text_allowed_attachment_class: type):
        """Test that from_file validates size against DEFAULT_MAX_ATTACHMENT_SIZE."""
        Attachment = text_allowed_attachment_class
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1))

        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_file(file_path=large_file, mime_type="text/plain")

    def test_from_file_toctou_protection(self, tmp_path: Path):
        """Test that from_file catches files that grow between stat and read."""
        from unittest.mock import MagicMock, patch

        small_max = 100
        Attachment = create_attachment_class(
            AttachmentConfig(
                max_size=small_max,
                allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
                validate_content=False,
            )
        )

        test_file = tmp_path / "growing.txt"
        test_file.write_bytes(b"x" * 50)  # Small enough to pass stat check

        # Mock Path.open to return more data than stat reported (simulates file growth)
        grown_content = b"x" * (small_max + 1)
        mock_file = MagicMock()
        mock_file.read.return_value = grown_content
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)

        with patch.object(Path, "open", return_value=mock_file):
            with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
                Attachment.from_file(file_path=test_file, mime_type="text/plain")

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
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")

        attachment = Attachment.from_file(file_path=pdf_file)
        assert attachment.mime_type == "application/pdf"

    def test_from_file_raises_file_not_found(self, tmp_path: Path, default_attachment_class: type):
        """Test that from_file raises FileNotFoundError for missing files."""
        Attachment = default_attachment_class
        with pytest.raises(FileNotFoundError):
            Attachment.from_file(file_path=tmp_path / "nonexistent.txt")


class TestEngineAttachment:
    """Tests for Engine.Attachment class."""

    def test_engine_exposes_attachment_class(self):
        """Test that Engine exposes an Attachment class."""
        config_data = {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {"TYPE": "json", "DATA": {"site_content": {"pages": []}}},
            "ATTACHMENT": {
                "allowed_mime_types": list(_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"}),
                "validate_content": False,
            },
        }
        config = Config.model_validate(config_data)
        db = db_from_config(config.db)  # type: ignore[arg-type]
        app = Engine(config, db, "test")

        assert hasattr(app, "Attachment")
        # Create an attachment using the engine's class
        attachment = app.Attachment("test.txt", b"hello", "text/plain")
        assert attachment.filename == "test.txt"

    def test_engine_attachment_uses_config(self):
        """Test that Engine.Attachment uses the configured settings."""
        config_data = {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {"TYPE": "json", "DATA": {"site_content": {"pages": []}}},
            "ATTACHMENT": {
                "max_size": 1000,
                "validate_content": False,
                "allowed_mime_types": list(_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"}),
            },
        }
        config = Config.model_validate(config_data)
        db = db_from_config(config.db)  # type: ignore[arg-type]
        engine = Engine(config, db, "test")

        # Should work within the custom max size
        attachment = engine.Attachment("test.txt", b"x" * 1000, "text/plain")
        assert len(attachment.content) == 1000

        # Should fail above the custom max size
        with pytest.raises(AttachmentSizeError):
            engine.Attachment("test.txt", b"x" * 1001, "text/plain")


@pytest.fixture
def text_allowed_test_app():
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
        },
    }
    config = Config.model_validate(config_data)
    db = db_from_config(config.db)  # type: ignore[arg-type]
    return Engine(config, db, "test")


class TestNotifierWithAttachments:
    """Tests for notifier functionality with attachments."""

    def test_notifier_receives_attachments(self, text_allowed_test_app: Engine):
        """Test that notifier with attachments receives them."""
        received_attachments: list[list[Any] | None] = []

        def notifier(message: str, attachments: list[Any] | None = None) -> None:
            del message  # unused
            received_attachments.append(attachments)

        attachment = text_allowed_test_app.Attachment("test.txt", b"hello", "text/plain")
        text_allowed_test_app.add_notifier_with_attachments(notifier)
        text_allowed_test_app.notify("test message", attachments=[attachment])

        assert received_attachments[0] is not None
        assert received_attachments[0][0].filename == "test.txt"

    def test_simple_notifier_works(self, text_allowed_test_app: Engine):
        """Test that simple notifier (message only) works."""
        received_messages: list[str] = []

        def simple_notifier(message: str) -> None:
            received_messages.append(message)

        text_allowed_test_app.add_notifier(simple_notifier)
        text_allowed_test_app.notify(
            "test message",
            attachments=[text_allowed_test_app.Attachment("test.txt", b"hello", "text/plain")],
        )

        assert received_messages == ["test message"]

    def test_mixed_notifiers(self, text_allowed_test_app: Engine):
        """Test mixed notifiers - some with attachments, some without."""
        simple_messages: list[str] = []
        attachment_notifier_data: list[list[Any] | None] = []

        def simple_notifier(message: str) -> None:
            simple_messages.append(message)

        def notifier_with_attachments(message: str, attachments: list[Any] | None = None) -> None:
            del message  # unused
            attachment_notifier_data.append(attachments)

        attachment = text_allowed_test_app.Attachment("test.txt", b"hello", "text/plain")
        text_allowed_test_app.add_notifier(simple_notifier)
        text_allowed_test_app.add_notifier_with_attachments(notifier_with_attachments)
        text_allowed_test_app.notify("test message", attachments=[attachment])

        assert simple_messages == ["test message"]
        assert attachment_notifier_data[0] is not None


class TestMagicByteValidation:
    """Tests for magic byte content validation."""

    @pytest.mark.parametrize(
        ("mime_type", "magic_bytes"),
        [
            ("image/png", b"\x89PNG\r\n\x1a\n"),
            ("image/jpeg", b"\xff\xd8\xff"),
            ("image/gif", b"GIF89a"),
            ("application/pdf", b"%PDF"),
            ("application/zip", b"PK\x03\x04"),
            ("application/gzip", b"\x1f\x8b\x08"),
            ("image/bmp", b"BM"),
            ("audio/ogg", b"OggS"),
        ],
    )
    def test_valid_magic_bytes(
        self, mime_type: str, magic_bytes: bytes, default_attachment_class: type
    ):
        """Test various MIME types with their correct magic bytes."""
        Attachment = default_attachment_class
        content = magic_bytes + b"rest of file data"
        attachment = Attachment(filename="file.bin", content=content, mime_type=mime_type)
        assert attachment.content == content

    @pytest.mark.parametrize(
        "mime_type",
        ["image/png", "image/jpeg", "image/gif", "application/pdf", "application/zip"],
    )
    def test_invalid_content_raises_error(self, mime_type: str, default_attachment_class: type):
        """Test various MIME types with invalid content."""
        Attachment = default_attachment_class
        with pytest.raises(ContentMismatchError):
            Attachment(
                filename="file.bin",
                content=b"INVALID CONTENT THAT DOES NOT MATCH ANY MAGIC BYTES",
                mime_type=mime_type,
            )

    def test_mismatched_content_type_raises_error(self, default_attachment_class: type):
        """Test that content recognized as different type than declared raises error."""
        Attachment = default_attachment_class
        # Provide valid PNG magic bytes but declare as PDF
        png_content = b"\x89PNG\r\n\x1a\n" + b"fake png data"
        with pytest.raises(ContentMismatchError, match="Detected types:"):
            Attachment(
                filename="fake.pdf",
                content=png_content,
                mime_type="application/pdf",
            )

    def test_allow_unrecognized_content_skips_validation(self):
        """Test that allow_unrecognized_content=True allows unidentifiable content."""
        Attachment = create_attachment_class(
            AttachmentConfig(
                allowed_mime_types=frozenset({"application/octet-stream"}),
                allow_unrecognized_content=True,
            )
        )
        attachment = Attachment(
            filename="file.bin",
            content=b"random unidentifiable content xyz123",
            mime_type="application/octet-stream",
        )
        assert attachment.content is not None

    def test_text_mime_types_skip_validation(self, text_allowed_attachment_class: type):
        """Test that text/* MIME types skip magic byte validation when allowed."""
        Attachment = text_allowed_attachment_class
        attachment = Attachment(filename="file.txt", content=b"Some text", mime_type="text/plain")
        assert attachment.content == b"Some text"

    def test_application_json_skips_validation(self):
        """Test that application/json skips magic byte validation when allowed."""
        Attachment = create_attachment_class(
            AttachmentConfig(
                allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"application/json"},
            )
        )
        attachment = Attachment(
            filename="data.json", content=b'{"key": "value"}', mime_type="application/json"
        )
        assert attachment.content is not None

    def test_empty_content_skips_validation(self, default_attachment_class: type):
        """Test that empty content skips magic byte validation."""
        Attachment = default_attachment_class
        attachment = Attachment(filename="empty.png", content=b"", mime_type="image/png")
        assert attachment.content == b""

    def test_validate_content_false_skips_validation(self):
        """Test that validate_content=False skips magic byte validation."""
        Attachment = create_attachment_class(AttachmentConfig(validate_content=False))
        attachment = Attachment(
            filename="image.png",
            content=b"invalid png content",
            mime_type="image/png",
        )
        assert attachment.content == b"invalid png content"



class TestAttachmentProtocol:
    """Tests for AttachmentProtocol implementation."""

    def test_attachment_implements_protocol(self, default_attachment_class: type):
        """Test that created Attachment class implements AttachmentProtocol."""
        Attachment = default_attachment_class
        attachment = Attachment(
            filename="test.pdf",
            content=b"%PDF-1.7 content",
            mime_type="application/pdf",
        )
        assert isinstance(attachment, AttachmentProtocol)


    def test_factory_return_type(self):
        """Test that create_attachment_class returns type."""
        Attachment = create_attachment_class(AttachmentConfig())
        # Verify it returns a class that can be used as expected
        assert hasattr(Attachment, "from_bytes")
        assert hasattr(Attachment, "from_file")


class TestTextMimeTypesNotAllowedByDefault:
    """Tests verifying text/* MIME types are not allowed by default."""

    @pytest.mark.parametrize(
        "mime_type",
        [
            "text/plain",
            "text/html",
            "text/csv",
            "text/xml",
            "text/css",
            "text/javascript",
            "text/markdown",
            "application/json",
            "application/xml",
            "application/rtf",
            "image/svg+xml",
        ],
    )
    def test_text_mime_types_not_allowed_by_default(
        self, mime_type: str, default_attachment_class: type
    ):
        """Test that text/* and related types are rejected by default."""
        Attachment = default_attachment_class
        with pytest.raises(ValueError, match="is not allowed"):
            Attachment(filename="test.file", content=b"content", mime_type=mime_type)

    def test_text_mime_types_can_be_explicitly_allowed(self):
        """Test that text types can be explicitly allowed via configuration."""
        Attachment = create_attachment_class(
            AttachmentConfig(
                allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
                validate_content=False,
            )
        )
        attachment = Attachment(filename="test.txt", content=b"Hello", mime_type="text/plain")
        assert attachment.mime_type == "text/plain"



class TestExtensionValidation:
    """Tests for blocked extension validation."""

    @pytest.mark.parametrize(
        "extension",
        [
            "exe",
            "dll",
            "scr",
            "msi",
            "bat",
            "cmd",
            "vbs",
            "ps1",
            "jar",
            "lnk",
            "hta",
            "app",
            "dmg",
            "deb",
            "rpm",
            "sh",
            "py",
            "rb",
            "pl",
        ],
    )
    def test_blocked_extensions_rejected(self, extension: str, default_attachment_class: type):
        """Test that dangerous extensions are rejected."""
        Attachment = default_attachment_class
        with pytest.raises(BlockedExtensionError, match="blocked extension"):
            Attachment(
                filename=f"malware.{extension}",
                content=b"content",
                mime_type="application/pdf",
            )

    def test_blocked_extension_case_insensitive(self, default_attachment_class: type):
        """Test that extension blocking is case insensitive."""
        Attachment = default_attachment_class
        for ext in ["EXE", "Exe", "eXe", "exe"]:
            with pytest.raises(BlockedExtensionError, match="blocked extension"):
                Attachment(filename=f"file.{ext}", content=b"content", mime_type="application/pdf")

    @pytest.mark.parametrize(
        "filename",
        ["document.pdf", "image.png", "archive.zip", "report.docx", "data.xlsx"],
    )
    def test_safe_extensions_allowed(self, filename: str, no_validation_attachment_class: type):
        """Test that safe extensions are allowed."""
        Attachment = no_validation_attachment_class
        # Determine appropriate mime type based on extension
        mime_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".zip": "application/zip",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        ext = "." + filename.rsplit(".", 1)[-1]
        mime_type = mime_types[ext]
        attachment = Attachment(filename=filename, content=b"content", mime_type=mime_type)
        assert attachment.filename == filename

    def test_no_extension_allowed(self, no_validation_attachment_class: type):
        """Test that files without extension are allowed."""
        Attachment = no_validation_attachment_class
        attachment = Attachment(filename="README", content=b"content", mime_type="application/pdf")
        assert attachment.filename == "README"

    def test_blocked_extension_checked_before_mime_type(self, default_attachment_class: type):
        """Test that extension is validated before MIME type."""
        Attachment = default_attachment_class
        # Use an invalid MIME type but blocked extension
        # If extension is checked first, we should get BlockedExtensionError
        with pytest.raises(BlockedExtensionError, match="blocked extension"):
            Attachment(
                filename="malware.exe",
                content=b"content",
                mime_type="invalid-mime-type",
            )

    def test_blocked_extension_error_attributes(self, default_attachment_class: type):
        """Test that BlockedExtensionError has correct attributes."""
        Attachment = default_attachment_class
        try:
            Attachment(filename="virus.exe", content=b"content", mime_type="application/pdf")
        except BlockedExtensionError as e:
            assert e.filename == "virus.exe"
            assert e.extension == "exe"
            assert "blocked extension" in str(e)

