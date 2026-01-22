import inspect
import logging
from pathlib import Path

import pytest

from platzky.attachment import (
    MAX_ATTACHMENT_SIZE,
    AttachmentSizeError,
    ContentMismatchError,
    create_attachment_class,
)
from platzky.attachment.mime_validation import DEFAULT_ALLOWED_MIME_TYPES
from platzky.config import AttachmentConfig, Config
from platzky.db.json_db import db_from_config
from platzky.engine import Engine
from tests.unit_tests.fake_app import test_app

test_app = test_app


@pytest.fixture
def default_attachment_class():
    """Create an Attachment class with default configuration."""
    return create_attachment_class(AttachmentConfig())


@pytest.fixture
def permissive_attachment_class():
    """Create an Attachment class that allows unrecognized content."""
    return create_attachment_class(
        AttachmentConfig(
            allow_unrecognized_content=True,
        )
    )


@pytest.fixture
def no_validation_attachment_class():
    """Create an Attachment class with content validation disabled."""
    return create_attachment_class(
        AttachmentConfig(
            validate_content=False,
        )
    )


class TestAttachment:
    """Tests for the Attachment dataclass validation."""

    def test_valid_attachment(self, default_attachment_class):
        """Test creating a valid attachment."""
        Attachment = default_attachment_class
        attachment = Attachment(
            filename="test.pdf",
            content=b"%PDF-1.7 content here",
            mime_type="application/pdf",
        )
        assert attachment.filename == "test.pdf"
        assert attachment.mime_type == "application/pdf"

    def test_empty_filename_raises_error(self, default_attachment_class):
        """Test that empty filename raises ValueError."""
        Attachment = default_attachment_class
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
        self, filename: str, expected: str, caplog: pytest.LogCaptureFixture, default_attachment_class
    ):
        """Test that path components are stripped from filename."""
        Attachment = default_attachment_class
        with caplog.at_level(logging.WARNING):
            attachment = Attachment(filename=filename, content=b"content", mime_type="text/plain")
        assert attachment.filename == expected

    def test_oversized_attachment_raises_error(self, default_attachment_class):
        """Test that attachment exceeding max size raises AttachmentSizeError."""
        Attachment = default_attachment_class
        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment(
                filename="large.bin",
                content=b"x" * (MAX_ATTACHMENT_SIZE + 1),
                mime_type="text/plain",
            )

    def test_max_size_attachment_allowed(self, default_attachment_class):
        """Test that attachment at exactly max size is allowed."""
        Attachment = default_attachment_class
        attachment = Attachment(
            filename="max.bin",
            content=b"x" * MAX_ATTACHMENT_SIZE,
            mime_type="text/plain",
        )
        assert len(attachment.content) == MAX_ATTACHMENT_SIZE

    def test_invalid_mime_type_format_raises_error(self, default_attachment_class):
        """Test that invalid MIME type format raises ValueError."""
        Attachment = default_attachment_class
        with pytest.raises(ValueError, match="Invalid MIME type format"):
            Attachment(filename="file.txt", content=b"content", mime_type="invalid")

    def test_disallowed_mime_type_raises_error(self, default_attachment_class):
        """Test that MIME type not in allowlist raises ValueError."""
        Attachment = default_attachment_class
        with pytest.raises(ValueError, match="is not allowed"):
            Attachment(
                filename="file.exe", content=b"content", mime_type="application/x-executable"
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

    @pytest.mark.parametrize(
        "mime_type",
        ["text/plain", "text/html", "image/png", "image/jpeg", "application/pdf"],
    )
    def test_common_mime_types_are_allowed(self, mime_type: str, no_validation_attachment_class):
        """Test that common MIME types are in the default allowlist."""
        Attachment = no_validation_attachment_class
        attachment = Attachment(
            filename="test.file", content=b"content", mime_type=mime_type
        )
        assert attachment.mime_type == mime_type

    def test_attachment_is_immutable(self, default_attachment_class):
        """Test that attachment is frozen (immutable)."""
        Attachment = default_attachment_class
        attachment = Attachment(filename="test.txt", content=b"content", mime_type="text/plain")
        with pytest.raises(AttributeError):
            attachment.filename = "changed.txt"  # type: ignore[misc]

    def test_default_allowed_mime_types_is_frozenset(self):
        """Test that DEFAULT_ALLOWED_MIME_TYPES is immutable."""
        assert isinstance(DEFAULT_ALLOWED_MIME_TYPES, frozenset)

    def test_attachment_size_error_is_value_error_subclass(self):
        """Test that AttachmentSizeError is a subclass of ValueError."""
        assert issubclass(AttachmentSizeError, ValueError)

    def test_custom_max_size(self):
        """Test that custom max_size is respected."""
        small_max = 100
        Attachment = create_attachment_class(
            AttachmentConfig(max_size=small_max)
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

    def test_from_bytes_creates_valid_attachment(self, default_attachment_class):
        """Test that from_bytes creates a valid attachment."""
        Attachment = default_attachment_class
        attachment = Attachment.from_bytes(
            content=b"content", filename="test.txt", mime_type="text/plain"
        )
        assert attachment.filename == "test.txt"

    def test_from_bytes_validates_size_before_creation(self, default_attachment_class):
        """Test that from_bytes validates size before object creation."""
        Attachment = default_attachment_class
        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_bytes(
                content=b"x" * (MAX_ATTACHMENT_SIZE + 1),
                filename="large.bin",
                mime_type="text/plain",
            )


class TestAttachmentFromFile:
    """Tests for the Attachment.from_file() factory method."""

    def test_from_file_creates_valid_attachment(self, tmp_path: Path, default_attachment_class):
        """Test that from_file creates a valid attachment."""
        Attachment = default_attachment_class
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello, World!")

        attachment = Attachment.from_file(file_path=test_file, mime_type="text/plain")
        assert attachment.filename == "test.txt"
        assert attachment.content == b"Hello, World!"

    def test_from_file_validates_size(self, tmp_path: Path, default_attachment_class):
        """Test that from_file validates size against MAX_ATTACHMENT_SIZE."""
        Attachment = default_attachment_class
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * (MAX_ATTACHMENT_SIZE + 1))

        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_file(file_path=large_file, mime_type="text/plain")

    def test_from_file_with_custom_filename(self, tmp_path: Path, default_attachment_class):
        """Test from_file with custom filename override."""
        Attachment = default_attachment_class
        test_file = tmp_path / "original.txt"
        test_file.write_bytes(b"content")

        attachment = Attachment.from_file(
            file_path=test_file, filename="custom.txt", mime_type="text/plain"
        )
        assert attachment.filename == "custom.txt"

    def test_from_file_guesses_mime_type(self, tmp_path: Path, no_validation_attachment_class):
        """Test that from_file guesses MIME type from filename."""
        Attachment = no_validation_attachment_class
        pdf_file = tmp_path / "document.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")

        attachment = Attachment.from_file(file_path=pdf_file)
        assert attachment.mime_type == "application/pdf"

    def test_from_file_raises_file_not_found(self, tmp_path: Path, default_attachment_class):
        """Test that from_file raises FileNotFoundError for missing files."""
        Attachment = default_attachment_class
        with pytest.raises(FileNotFoundError):
            Attachment.from_file(file_path=tmp_path / "nonexistent.txt")


class TestEngineAttachment:
    """Tests for Engine.Attachment class."""

    def test_engine_exposes_attachment_class(self, test_app: Engine):
        """Test that Engine exposes an Attachment class."""
        assert hasattr(test_app, "Attachment")
        # Create an attachment using the engine's class
        attachment = test_app.Attachment("test.txt", b"hello", "text/plain")
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


class TestNotifierWithAttachments:
    """Tests for notifier functionality with attachments."""

    def test_notifier_receives_attachments(self, test_app: Engine):
        """Test that notifier with attachments parameter receives them."""
        received_attachments: list[list | None] = []

        def notifier(_message: str, attachments: list | None = None) -> None:
            received_attachments.append(attachments)

        attachment = test_app.Attachment("test.txt", b"hello", "text/plain")
        test_app.add_notifier(notifier)
        test_app.notify("test message", attachments=[attachment])

        assert received_attachments[0] is not None
        assert received_attachments[0][0].filename == "test.txt"

    def test_legacy_notifier_still_works(self, test_app: Engine):
        """Test that legacy notifier without attachments parameter still works."""
        received_messages: list[str] = []

        def legacy_notifier(message: str) -> None:
            received_messages.append(message)

        test_app.add_notifier(legacy_notifier)  # type: ignore[arg-type]
        test_app.notify("test message", attachments=[
            test_app.Attachment("test.txt", b"hello", "text/plain")
        ])

        assert received_messages == ["test message"]

    def test_mixed_notifiers(self, test_app: Engine):
        """Test mixed notifiers - some with attachments, some without."""
        legacy_messages: list[str] = []
        modern_attachments: list[list | None] = []

        def legacy_notifier(message: str) -> None:
            legacy_messages.append(message)

        def modern_notifier(_message: str, attachments: list | None = None) -> None:
            modern_attachments.append(attachments)

        attachment = test_app.Attachment("test.txt", b"hello", "text/plain")
        test_app.add_notifier(legacy_notifier)  # type: ignore[arg-type]
        test_app.add_notifier(modern_notifier)
        test_app.notify("test message", attachments=[attachment])

        assert legacy_messages == ["test message"]
        assert modern_attachments[0] is not None

    def test_kwargs_notifier_receives_attachments(self, test_app: Engine):
        """Test that notifiers with **kwargs receive attachments."""
        received: list[list | None] = []

        def kwargs_notifier(_message: str, **kwargs: object) -> None:
            received.append(kwargs.get("attachments"))  # type: ignore[arg-type]

        attachment = test_app.Attachment("test.txt", b"hello", "text/plain")
        test_app.add_notifier(kwargs_notifier)  # type: ignore[arg-type]
        test_app.notify("test", attachments=[attachment])

        assert received[0] is not None
        assert received[0][0].filename == "test.txt"


class TestNotifierCapabilityCache:
    """Tests for notifier capability caching."""

    def test_cache_avoids_repeated_signature_inspection(self, test_app: Engine):
        """Test that signature inspection is only called once per notifier."""
        from unittest.mock import patch

        def notifier(_message: str, _attachments: list | None = None) -> None:
            pass

        test_app.add_notifier(notifier)

        with patch("platzky.engine.inspect.signature", wraps=inspect.signature) as mock_sig:
            test_app.notify("test1")
            test_app.notify("test2")
            assert mock_sig.call_count == 1

    def test_clear_notifier_cache_triggers_reinspection(self, test_app: Engine):
        """Test that clear_notifier_cache causes signature to be inspected again."""
        from unittest.mock import patch

        def notifier(_message: str) -> None:
            pass

        test_app.add_notifier(notifier)  # type: ignore[arg-type]

        with patch("platzky.engine.inspect.signature", wraps=inspect.signature) as mock_sig:
            test_app.notify("test1")
            test_app.clear_notifier_cache()
            test_app.notify("test2")
            assert mock_sig.call_count == 2

    def test_cache_is_engine_instance_specific(self):
        """Test that cache is instance-specific, not shared across Engine instances."""
        from unittest.mock import patch

        config_data = {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {"TYPE": "json", "DATA": {"site_content": {"pages": []}}},
        }
        config = Config.model_validate(config_data)
        db = db_from_config(config.db)  # type: ignore[arg-type]

        engine1 = Engine(config, db, "test1")
        engine2 = Engine(config, db, "test2")

        def notifier(_message: str) -> None:
            pass

        engine1.add_notifier(notifier)  # type: ignore[arg-type]
        engine2.add_notifier(notifier)  # type: ignore[arg-type]

        with patch("platzky.engine.inspect.signature", wraps=inspect.signature) as mock_sig:
            engine1.notify("test")
            engine2.notify("test")
            assert mock_sig.call_count == 2


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
    def test_valid_magic_bytes(self, mime_type: str, magic_bytes: bytes, default_attachment_class):
        """Test various MIME types with their correct magic bytes."""
        Attachment = default_attachment_class
        content = magic_bytes + b"rest of file data"
        attachment = Attachment(filename="file.bin", content=content, mime_type=mime_type)
        assert attachment.content == content

    @pytest.mark.parametrize(
        "mime_type",
        ["image/png", "image/jpeg", "image/gif", "application/pdf", "application/zip"],
    )
    def test_invalid_content_raises_error(self, mime_type: str, default_attachment_class):
        """Test various MIME types with invalid content."""
        Attachment = default_attachment_class
        with pytest.raises(ContentMismatchError):
            Attachment(
                filename="file.bin",
                content=b"INVALID CONTENT THAT DOES NOT MATCH ANY MAGIC BYTES",
                mime_type=mime_type,
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

    def test_text_mime_types_skip_validation(self, default_attachment_class):
        """Test that text/* MIME types skip magic byte validation."""
        Attachment = default_attachment_class
        attachment = Attachment(filename="file.txt", content=b"Some text", mime_type="text/plain")
        assert attachment.content == b"Some text"

    def test_application_json_skips_validation(self, default_attachment_class):
        """Test that application/json skips magic byte validation."""
        Attachment = default_attachment_class
        attachment = Attachment(
            filename="data.json", content=b'{"key": "value"}', mime_type="application/json"
        )
        assert attachment.content is not None

    def test_empty_content_skips_validation(self, default_attachment_class):
        """Test that empty content skips magic byte validation."""
        Attachment = default_attachment_class
        attachment = Attachment(filename="empty.png", content=b"", mime_type="image/png")
        assert attachment.content == b""

    def test_validate_content_false_skips_validation(self):
        """Test that validate_content=False skips magic byte validation."""
        Attachment = create_attachment_class(
            AttachmentConfig(validate_content=False)
        )
        attachment = Attachment(
            filename="image.png",
            content=b"invalid png content",
            mime_type="image/png",
        )
        assert attachment.content == b"invalid png content"

    def test_content_mismatch_error_is_value_error(self):
        """Test that ContentMismatchError is a subclass of ValueError."""
        assert issubclass(ContentMismatchError, ValueError)
