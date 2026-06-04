"""Tests for attachment functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from platzky.attachment import (
    DEFAULT_MAX_ATTACHMENT_SIZE,
    Attachment,
    AttachmentSizeError,
    BlockedExtensionError,
    ContentMismatchError,
    ExtensionNotAllowedError,
    InvalidMimeTypeError,
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
def default_config() -> AttachmentConfig:
    """Attachment config with default settings and common extensions."""
    return AttachmentConfig(
        allowed_extensions=frozenset({"pdf", "png", "jpg", "gif", "zip", "bin"}),
    )


@pytest.fixture
def no_validation_config() -> AttachmentConfig:
    """Attachment config with content validation disabled."""
    return AttachmentConfig(
        validate_content=False,
        allowed_extensions=frozenset({"pdf", "png", "zip", "docx", "xlsx", "txt", "bin"}),
    )


@pytest.fixture
def text_allowed_config() -> AttachmentConfig:
    """Attachment config with text types allowed."""
    return AttachmentConfig(
        allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
        validate_content=False,
        allowed_extensions=frozenset({"txt", "bin", "pdf", "png"}),
    )


class TestAttachmentBasics:
    """Core attachment creation and validation tests."""

    def test_valid_attachment(self, default_config: AttachmentConfig):
        """Test creating a valid attachment."""
        attachment = Attachment.create(
            filename="test.pdf",
            content=b"%PDF-1.7 content here",
            mime_type="application/pdf",
            config=default_config,
        )
        assert attachment.filename == "test.pdf"
        assert attachment.mime_type == "application/pdf"
        assert isinstance(attachment, Attachment)

    def test_empty_filename_raises_error(self, text_allowed_config: AttachmentConfig):
        """Test that empty filename raises ValueError."""
        with pytest.raises(ValueError, match="filename cannot be empty"):
            Attachment.create("", b"content", "text/plain", text_allowed_config)

    @pytest.mark.parametrize("filename", [".", "..", "/", "//"])
    def test_invalid_filenames_rejected(self, filename: str, text_allowed_config: AttachmentConfig):
        """Test that directory traversal filenames are rejected."""
        with pytest.raises(ValueError, match="filename cannot be empty"):
            Attachment.create(filename, b"c", "text/plain", text_allowed_config)

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("../../../etc/secret.txt", "secret.txt"),
            ("/etc/config.txt", "config.txt"),
            ("C:\\Users\\test\\file.txt", "file.txt"),
        ],
    )
    def test_path_sanitization(
        self,
        filename: str,
        expected: str,
        text_allowed_config: AttachmentConfig,
    ):
        """Test that path components are stripped from filename."""
        attachment = Attachment.create(filename, b"content", "text/plain", text_allowed_config)
        assert attachment.filename == expected

    def test_size_validation(self, text_allowed_config: AttachmentConfig):
        """Test attachment size limits."""
        # Exactly at max size - should work
        attachment = Attachment.create(
            "max.bin",
            b"x" * DEFAULT_MAX_ATTACHMENT_SIZE,
            "text/plain",
            text_allowed_config,
        )
        assert len(attachment.content) == DEFAULT_MAX_ATTACHMENT_SIZE

        # Over max size - should fail
        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.create(
                "large.bin",
                b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1),
                "text/plain",
                text_allowed_config,
            )

    def test_custom_max_size(self):
        """Test that custom max_size is respected."""
        config = AttachmentConfig(
            max_size=100,
            allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
            validate_content=False,
            allowed_extensions=frozenset({"txt"}),
        )
        # At limit - works
        assert len(Attachment.create("s.txt", b"x" * 100, "text/plain", config).content) == 100
        # Over limit - fails
        with pytest.raises(AttachmentSizeError):
            Attachment.create("big.txt", b"x" * 101, "text/plain", config)

    def test_mime_type_validation(self, default_config: AttachmentConfig):
        """Test MIME type validation."""
        # Invalid format
        with pytest.raises(InvalidMimeTypeError, match="Invalid MIME type format") as exc_info:
            Attachment.create("file.pdf", b"content", "invalid", default_config)
        assert exc_info.value.invalid_format is True

        # Not in allowlist
        with pytest.raises(InvalidMimeTypeError, match="is not allowed") as exc_info:
            Attachment.create("file.bin", b"content", "application/x-executable", default_config)
        assert exc_info.value.invalid_format is False


class TestAttachmentFactoryMethods:
    """Tests for from_bytes() and from_file() factory methods."""

    def test_from_bytes(self, text_allowed_config: AttachmentConfig):
        """Test from_bytes creates valid attachment and validates size."""
        attachment = Attachment.from_bytes(
            content=b"content",
            filename="test.txt",
            mime_type="text/plain",
            config=text_allowed_config,
        )
        assert attachment.filename == "test.txt"

        # Size validation
        with pytest.raises(AttachmentSizeError):
            Attachment.from_bytes(
                content=b"x" * (DEFAULT_MAX_ATTACHMENT_SIZE + 1),
                filename="large.bin",
                mime_type="text/plain",
                config=text_allowed_config,
            )

    def test_from_file(self, tmp_path: Path, text_allowed_config: AttachmentConfig):
        """Test from_file creates valid attachment."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello, World!")

        attachment = Attachment.from_file(
            file_path=test_file, config=text_allowed_config, mime_type="text/plain"
        )
        assert attachment.filename == "test.txt"
        assert attachment.content == b"Hello, World!"

    def test_from_file_with_custom_filename(
        self, tmp_path: Path, text_allowed_config: AttachmentConfig
    ):
        """Test from_file with custom filename override."""
        test_file = tmp_path / "original.txt"
        test_file.write_bytes(b"content")

        attachment = Attachment.from_file(
            file_path=test_file,
            config=text_allowed_config,
            filename="custom.txt",
            mime_type="text/plain",
        )
        assert attachment.filename == "custom.txt"

    def test_from_file_guesses_mime_type(
        self, tmp_path: Path, no_validation_config: AttachmentConfig
    ):
        """Test that from_file guesses MIME type from filename."""
        pdf_file = tmp_path / "document.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf")

        attachment = Attachment.from_file(file_path=pdf_file, config=no_validation_config)
        assert attachment.mime_type == "application/pdf"

    def test_from_file_toctou_protection(self, tmp_path: Path):
        """Test that from_file catches files that grow between stat and read."""
        config = AttachmentConfig(
            max_size=100,
            allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
            validate_content=False,
            allowed_extensions=frozenset({"txt"}),
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
                Attachment.from_file(file_path=test_file, config=config, mime_type="text/plain")

    def test_max_size_override(self, tmp_path: Path):
        """Test max_size_override for both from_bytes and from_file."""
        config = AttachmentConfig(
            max_size=100,
            allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
            validate_content=False,
            allowed_extensions=frozenset({"txt"}),
        )

        # from_bytes: override allows larger content
        attachment = Attachment.from_bytes(
            content=b"x" * 200,
            filename="large.txt",
            mime_type="text/plain",
            config=config,
            max_size_override=500,
        )
        assert len(attachment.content) == 200

        # from_bytes: override still enforced
        with pytest.raises(AttachmentSizeError):
            Attachment.from_bytes(
                content=b"x" * 600,
                filename="huge.txt",
                mime_type="text/plain",
                config=config,
                max_size_override=500,
            )

        # from_file: same behavior
        large_file = tmp_path / "large.txt"
        large_file.write_bytes(b"x" * 200)
        attachment = Attachment.from_file(
            file_path=large_file, config=config, mime_type="text/plain", max_size_override=500
        )
        assert len(attachment.content) == 200


class TestEngineAttachment:
    """Tests for Engine attachment integration."""

    def test_engine_exposes_attachment_class(self):
        """Test that Engine exposes attachment creation methods."""
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
        attachment = engine.create_attachment("test.txt", b"hello", "text/plain")
        assert attachment.filename == "test.txt"

        # Respects configured max_size
        with pytest.raises(AttachmentSizeError):
            engine.create_attachment("test.txt", b"x" * 1001, "text/plain")


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
        self, mime_type: str, magic_bytes: bytes, default_config: AttachmentConfig
    ):
        """Test MIME types with correct magic bytes are accepted."""
        content = magic_bytes + b"rest of file data"
        attachment = Attachment.create("file.bin", content, mime_type, default_config)
        assert attachment.content == content

    @pytest.mark.parametrize("mime_type", ["image/png", "image/jpeg", "application/pdf"])
    def test_invalid_content_raises_error(self, mime_type: str, default_config: AttachmentConfig):
        """Test MIME types with invalid content are rejected."""
        with pytest.raises(ContentMismatchError):
            Attachment.create("file.bin", b"INVALID CONTENT", mime_type, default_config)

    def test_mismatched_content_type_raises_error(self, default_config: AttachmentConfig):
        """Test that content recognized as different type raises error."""
        # Valid PNG magic bytes but declared as PDF
        png_content = b"\x89PNG\r\n\x1a\n" + b"fake png data"
        with pytest.raises(ContentMismatchError, match="Detected types:"):
            Attachment.create("fake.pdf", png_content, "application/pdf", default_config)

    def test_validation_bypass_options(self):
        """Test various ways to bypass content validation."""
        config1 = AttachmentConfig(
            allowed_mime_types=frozenset({"application/octet-stream"}),
            allow_unrecognized_content=True,
            allowed_extensions=frozenset({"bin"}),
        )
        assert (
            Attachment.create("f.bin", b"random xyz", "application/octet-stream", config1).content
            is not None
        )

        config2 = AttachmentConfig(validate_content=False, allowed_extensions=frozenset({"png"}))
        assert Attachment.create("i.png", b"invalid", "image/png", config2).content == b"invalid"

        # Empty content skips validation
        config3 = AttachmentConfig(allowed_extensions=frozenset({"png"}))
        assert Attachment.create("empty.png", b"", "image/png", config3).content == b""


class TestMimeTypeRestrictions:
    """Tests for MIME type restrictions."""

    @pytest.mark.parametrize(
        "mime_type",
        ["text/plain", "text/html", "application/json", "image/svg+xml"],
    )
    def test_text_types_not_allowed_by_default(
        self, mime_type: str, default_config: AttachmentConfig
    ):
        """Test that text/* and related types are rejected by default."""
        with pytest.raises(ValueError, match="is not allowed"):
            Attachment.create("test.bin", b"content", mime_type, default_config)

    def test_text_types_can_be_explicitly_allowed(self):
        """Test that text types can be explicitly allowed."""
        config = AttachmentConfig(
            allowed_mime_types=_DEFAULT_ALLOWED_MIME_TYPES | {"text/plain"},
            validate_content=False,
            allowed_extensions=frozenset({"txt"}),
        )
        attachment = Attachment.create("test.txt", b"Hello", "text/plain", config)
        assert attachment.mime_type == "text/plain"


class TestExtensionValidation:
    """Tests for file extension validation (blocking and allowing)."""

    @pytest.mark.parametrize("extension", ["exe", "bat", "ps1", "sh", "py", "jar"])
    def test_blocked_extensions_rejected(self, extension: str, default_config: AttachmentConfig):
        """Test that dangerous extensions are rejected."""
        with pytest.raises(BlockedExtensionError, match="blocked extension"):
            Attachment.create(f"malware.{extension}", b"content", "application/pdf", default_config)

    def test_blocked_extension_case_insensitive(self, default_config: AttachmentConfig):
        """Test that extension blocking is case insensitive."""
        for ext in ["EXE", "Exe", "exe"]:
            with pytest.raises(BlockedExtensionError):
                Attachment.create(f"file.{ext}", b"c", "application/pdf", default_config)

    def test_blocked_extension_checked_before_mime_type(self, default_config: AttachmentConfig):
        """Test that extension is validated before MIME type."""
        with pytest.raises(BlockedExtensionError):
            Attachment.create("malware.exe", b"c", "invalid", default_config)

    def test_blocked_extension_error_attributes(self, default_config: AttachmentConfig):
        """Test BlockedExtensionError attributes."""
        with pytest.raises(BlockedExtensionError) as exc_info:
            Attachment.create("virus.exe", b"c", "application/pdf", default_config)
        assert exc_info.value.filename == "virus.exe"
        assert exc_info.value.extension == "exe"

    def test_blocked_takes_precedence_over_allowed(self):
        """Test that blocked_extensions takes precedence over allowed_extensions."""
        config = AttachmentConfig(
            validate_content=False,
            blocked_extensions=frozenset({"exe"}),
            allowed_extensions=frozenset({"exe", "pdf"}),
        )
        with pytest.raises(BlockedExtensionError):
            Attachment.create("app.exe", b"content", "application/pdf", config)
        # pdf should work
        assert (
            Attachment.create("doc.pdf", b"%PDF", "application/pdf", config).filename == "doc.pdf"
        )

    @pytest.mark.parametrize(
        "filename", ["document.pdf", "image.png", "archive.zip", "report.docx"]
    )
    def test_safe_extensions_allowed(self, filename: str, no_validation_config: AttachmentConfig):
        """Test that safe extensions are allowed."""
        mime_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".zip": "application/zip",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        ext = "." + filename.rsplit(".", 1)[-1]
        attachment = Attachment.create(filename, b"c", mime_types[ext], no_validation_config)
        assert attachment.filename == filename


class TestExtensionAllowList:
    """Tests for extension allow-list functionality."""

    def test_allowed_extensions_none_or_empty_blocks_all(self):
        """Test that None or empty allowed_extensions blocks all extensions."""
        for allowed in [None, frozenset()]:
            config = AttachmentConfig(validate_content=False, allowed_extensions=allowed)
            with pytest.raises(ExtensionNotAllowedError):
                Attachment.create("file.pdf", b"content", "application/pdf", config)

    def test_allowed_extensions_filtering(self):
        """Test that only listed extensions are allowed."""
        config = AttachmentConfig(
            validate_content=False, allowed_extensions=frozenset({"pdf", "png"})
        )
        # Allowed
        assert (
            Attachment.create("doc.pdf", b"%PDF", "application/pdf", config).filename == "doc.pdf"
        )
        # Not allowed
        with pytest.raises(ExtensionNotAllowedError, match="not in the allowed"):
            Attachment.create("image.gif", b"content", "image/gif", config)

    def test_no_extension_blocked_when_allow_list_set(self):
        """Test that files without extension are blocked when allow-list is set."""
        config = AttachmentConfig(validate_content=False, allowed_extensions=frozenset({"pdf"}))
        with pytest.raises(ExtensionNotAllowedError, match="no file extension"):
            Attachment.create("README", b"content", "application/pdf", config)

    def test_extension_not_allowed_error_attributes(self):
        """Test ExtensionNotAllowedError attributes."""
        config = AttachmentConfig(validate_content=False, allowed_extensions=frozenset({"pdf"}))
        # With extension
        with pytest.raises(ExtensionNotAllowedError) as exc_info:
            Attachment.create("image.png", b"content", "image/png", config)
        assert exc_info.value.filename == "image.png"
        assert exc_info.value.extension == "png"

        # Without extension
        with pytest.raises(ExtensionNotAllowedError) as exc_info:
            Attachment.create("README", b"content", "application/pdf", config)
        assert exc_info.value.extension is None

    def test_allowed_extensions_case_insensitive(self):
        """Test that extension matching is case-insensitive."""
        config = AttachmentConfig(validate_content=False, allowed_extensions=frozenset({"pdf"}))
        assert (
            Attachment.create("document.PDF", b"%PDF", "application/pdf", config).filename
            == "document.PDF"
        )

    def test_default_allowed_extensions_work(self):
        """Test that the default allowed_extensions allow common file types."""
        config = AttachmentConfig(validate_content=False)

        # Common extensions should work
        assert Attachment.create("photo.png", b"c", "image/png", config).filename == "photo.png"
        assert Attachment.create("doc.pdf", b"c", "application/pdf", config).filename == "doc.pdf"
        assert Attachment.create("data.zip", b"c", "application/zip", config).filename == "data.zip"

        # Extensions not in default list should be rejected
        with pytest.raises(ExtensionNotAllowedError):
            Attachment.create("code.json", b"{}", "application/json", config)
