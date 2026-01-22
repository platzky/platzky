import inspect
import logging
from pathlib import Path

import pytest

from platzky.config import Config
from platzky.db.json_db import Json
from platzky.engine import Engine
from platzky.notifier import (
    DEFAULT_ALLOWED_MIME_TYPES,
    MAX_ATTACHMENT_SIZE,
    MAGIC_BYTES,
    Attachment,
    AttachmentSizeError,
    ContentMismatchError,
)
from tests.unit_tests.fake_app import test_app

test_app = test_app


# =============================================================================
# Attachment Tests
# =============================================================================


class TestAttachment:
    """Tests for the Attachment dataclass validation."""

    def test_valid_attachment(self):
        """Test creating a valid attachment."""
        pdf_content = b"%PDF-1.7 content here"
        attachment = Attachment(
            filename="test.pdf",
            content=pdf_content,
            mime_type="application/pdf",
        )
        assert attachment.filename == "test.pdf"
        assert attachment.content == pdf_content
        assert attachment.mime_type == "application/pdf"

    def test_empty_filename_raises_error(self):
        """Test that empty filename raises ValueError."""
        with pytest.raises(ValueError, match="filename cannot be empty"):
            Attachment(filename="", content=b"content", mime_type="text/plain")

    def test_path_traversal_sanitized(self, caplog: pytest.LogCaptureFixture):
        """Test that path components are stripped from filename."""
        with caplog.at_level(logging.WARNING):
            attachment = Attachment(
                filename="../../../etc/passwd",
                content=b"malicious",
                mime_type="text/plain",
            )
        assert attachment.filename == "passwd"
        assert "path components" in caplog.text

    def test_absolute_path_sanitized(self, caplog: pytest.LogCaptureFixture):
        """Test that absolute paths are sanitized."""
        with caplog.at_level(logging.WARNING):
            attachment = Attachment(
                filename="/etc/passwd",
                content=b"content",
                mime_type="text/plain",
            )
        assert attachment.filename == "passwd"

    def test_windows_path_sanitized(self, caplog: pytest.LogCaptureFixture):
        """Test that Windows-style paths are sanitized."""
        with caplog.at_level(logging.WARNING):
            attachment = Attachment(
                filename="C:\\Users\\test\\file.txt",
                content=b"content",
                mime_type="text/plain",
            )
        assert "/" not in attachment.filename
        assert "\\" not in attachment.filename

    def test_oversized_attachment_raises_error(self):
        """Test that attachment exceeding max size raises ValueError."""
        oversized_content = b"x" * (MAX_ATTACHMENT_SIZE + 1)
        with pytest.raises(ValueError, match="exceeds maximum size"):
            Attachment(
                filename="large.bin",
                content=oversized_content,
                mime_type="application/zip",
                validate_content=False,
            )

    def test_max_size_attachment_allowed(self):
        """Test that attachment at exactly max size is allowed."""
        max_content = b"x" * MAX_ATTACHMENT_SIZE
        attachment = Attachment(
            filename="max.bin",
            content=max_content,
            mime_type="application/zip",
            validate_content=False,
        )
        assert len(attachment.content) == MAX_ATTACHMENT_SIZE

    def test_max_attachment_size_constant(self):
        """Test that MAX_ATTACHMENT_SIZE has the expected value."""
        assert MAX_ATTACHMENT_SIZE == 10 * 1024 * 1024  # 10MB

    def test_attachment_size_error_is_value_error_subclass(self):
        """Test that AttachmentSizeError is a subclass of ValueError."""
        assert issubclass(AttachmentSizeError, ValueError)

    def test_invalid_mime_type_format_raises_error(self):
        """Test that invalid MIME type format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid MIME type format"):
            Attachment(filename="file.txt", content=b"content", mime_type="invalid")

    def test_empty_mime_type_raises_error(self):
        """Test that empty MIME type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid MIME type format"):
            Attachment(filename="file.txt", content=b"content", mime_type="")

    def test_disallowed_mime_type_raises_error(self):
        """Test that MIME type not in allowlist raises ValueError."""
        with pytest.raises(ValueError, match="is not allowed"):
            Attachment(
                filename="file.exe",
                content=b"content",
                mime_type="application/x-executable",
            )

    def test_custom_allowed_mime_types_extends_default(self):
        """Test that custom allowed_mime_types extends the default list."""
        custom_type = "application/x-custom"
        attachment = Attachment(
            filename="custom.file",
            content=b"content",
            mime_type=custom_type,
            allowed_mime_types=frozenset({custom_type}),
        )
        assert attachment.mime_type == custom_type

    def test_default_allowed_mime_types_still_work_with_custom(self):
        """Test that default MIME types still work when custom types are provided."""
        attachment = Attachment(
            filename="file.pdf",
            content=b"%PDF-1.7 content",
            mime_type="application/pdf",
            allowed_mime_types=frozenset({"application/x-custom"}),
        )
        assert attachment.mime_type == "application/pdf"

    @pytest.mark.parametrize(
        "mime_type",
        [
            "text/plain",
            "text/html",
            "text/csv",
            "image/png",
            "image/jpeg",
            "image/gif",
            "application/pdf",
            "application/json",
            "application/xml",
            "application/zip",
        ],
    )
    def test_common_mime_types_are_allowed(self, mime_type: str):
        """Test that common MIME types are in the default allowlist."""
        attachment = Attachment(
            filename="test.file",
            content=b"content",
            mime_type=mime_type,
            validate_content=False,
        )
        assert attachment.mime_type == mime_type

    def test_default_allowed_mime_types_constant_is_frozenset(self):
        """Test that DEFAULT_ALLOWED_MIME_TYPES is immutable."""
        assert isinstance(DEFAULT_ALLOWED_MIME_TYPES, frozenset)

    def test_mime_type_validation_with_malicious_format(self):
        """Test that MIME types with valid format but not in allowlist are rejected."""
        with pytest.raises(ValueError, match="is not allowed"):
            Attachment(
                filename="script.sh",
                content=b"#!/bin/bash",
                mime_type="application/x-shellscript",
            )

    def test_attachment_is_immutable(self):
        """Test that attachment is frozen (immutable)."""
        attachment = Attachment(filename="test.txt", content=b"content", mime_type="text/plain")
        with pytest.raises(AttributeError):
            attachment.filename = "changed.txt"  # type: ignore[misc]


# =============================================================================
# Attachment Factory Methods Tests
# =============================================================================


class TestAttachmentFromBytes:
    """Tests for the Attachment.from_bytes() factory method."""

    def test_from_bytes_creates_valid_attachment(self):
        """Test that from_bytes creates a valid attachment."""
        content = b"PDF content here"
        attachment = Attachment.from_bytes(
            content=content,
            filename="test.pdf",
            mime_type="application/pdf",
            validate_content=False,
        )
        assert attachment.filename == "test.pdf"
        assert attachment.content == content
        assert attachment.mime_type == "application/pdf"

    def test_from_bytes_validates_size(self):
        """Test that from_bytes validates size against MAX_ATTACHMENT_SIZE."""
        oversized_content = b"x" * (MAX_ATTACHMENT_SIZE + 1)
        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_bytes(
                content=oversized_content,
                filename="large.bin",
                mime_type="application/zip",
            )

    def test_from_bytes_sanitizes_filename(self, caplog: pytest.LogCaptureFixture):
        """Test that from_bytes sanitizes filenames with path components."""
        with caplog.at_level(logging.WARNING):
            attachment = Attachment.from_bytes(
                content=b"content",
                filename="../../../etc/passwd",
                mime_type="text/plain",
            )
        assert attachment.filename == "passwd"
        assert "path components" in caplog.text

    def test_from_bytes_raises_on_empty_filename(self):
        """Test that from_bytes raises on empty filename."""
        with pytest.raises(ValueError, match="filename cannot be empty"):
            Attachment.from_bytes(
                content=b"content",
                filename="",
                mime_type="text/plain",
            )

    def test_from_bytes_raises_on_invalid_mime_type(self):
        """Test that from_bytes raises on invalid MIME type."""
        with pytest.raises(ValueError, match="Invalid MIME type"):
            Attachment.from_bytes(
                content=b"content",
                filename="test.bin",
                mime_type="invalid",
            )

    def test_from_bytes_with_allowed_mime_types(self):
        """Test from_bytes with custom allowed_mime_types."""
        custom_type = "application/x-custom"
        attachment = Attachment.from_bytes(
            content=b"content",
            filename="test.custom",
            mime_type=custom_type,
            allowed_mime_types=frozenset({custom_type}),
        )
        assert attachment.mime_type == custom_type


class TestAttachmentFromFile:
    """Tests for the Attachment.from_file() factory method."""

    def test_from_file_creates_valid_attachment(self, tmp_path: Path):
        """Test that from_file creates a valid attachment."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello, World!")

        attachment = Attachment.from_file(
            file_path=test_file,
            mime_type="text/plain",
        )
        assert attachment.filename == "test.txt"
        assert attachment.content == b"Hello, World!"
        assert attachment.mime_type == "text/plain"

    def test_from_file_validates_size(self, tmp_path: Path):
        """Test that from_file validates size against MAX_ATTACHMENT_SIZE."""
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * (MAX_ATTACHMENT_SIZE + 1))

        with pytest.raises(AttachmentSizeError, match="exceeds maximum size"):
            Attachment.from_file(
                file_path=large_file,
                mime_type="application/zip",
            )

    def test_from_file_with_custom_filename(self, tmp_path: Path):
        """Test from_file with custom filename override."""
        test_file = tmp_path / "original.txt"
        test_file.write_bytes(b"content")

        attachment = Attachment.from_file(
            file_path=test_file,
            filename="custom.txt",
            mime_type="text/plain",
        )
        assert attachment.filename == "custom.txt"

    def test_from_file_uses_basename_when_no_filename(self, tmp_path: Path):
        """Test that from_file uses file basename when filename is None."""
        test_file = tmp_path / "myfile.txt"
        test_file.write_bytes(b"content")

        attachment = Attachment.from_file(
            file_path=test_file,
            filename=None,
            mime_type="text/plain",
        )
        assert attachment.filename == "myfile.txt"

    def test_from_file_guesses_mime_type(self, tmp_path: Path):
        """Test that from_file guesses MIME type from filename."""
        pdf_file = tmp_path / "document.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")

        attachment = Attachment.from_file(
            file_path=pdf_file,
            mime_type=None,
            validate_content=False,
        )
        assert attachment.mime_type == "application/pdf"

    def test_from_file_falls_back_to_octet_stream(self, tmp_path: Path):
        """Test that from_file falls back to application/octet-stream for unknown types."""
        unknown_file = tmp_path / "unknown.xyz123"
        unknown_file.write_bytes(b"content")

        attachment = Attachment.from_file(
            file_path=unknown_file,
            mime_type=None,
            allowed_mime_types=frozenset({"application/octet-stream"}),
        )
        assert attachment.mime_type == "application/octet-stream"

    def test_from_file_raises_file_not_found(self, tmp_path: Path):
        """Test that from_file raises FileNotFoundError for missing files."""
        missing_file = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            Attachment.from_file(file_path=missing_file)

    def test_from_file_raises_is_directory_error(self, tmp_path: Path):
        """Test that from_file raises error when path is a directory."""
        directory = tmp_path / "subdir"
        directory.mkdir()

        with pytest.raises((IsADirectoryError, PermissionError)):
            Attachment.from_file(file_path=directory)

    def test_from_file_with_path_object(self, tmp_path: Path):
        """Test from_file with Path object instead of string."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"content")

        attachment1 = Attachment.from_file(
            file_path=str(test_file),
            mime_type="text/plain",
        )
        attachment2 = Attachment.from_file(
            file_path=test_file,
            mime_type="text/plain",
        )

        assert attachment1.content == attachment2.content
        assert attachment1.filename == attachment2.filename

    def test_from_file_with_allowed_mime_types(self, tmp_path: Path):
        """Test from_file with custom allowed_mime_types."""
        custom_file = tmp_path / "custom.file"
        custom_file.write_bytes(b"content")

        custom_type = "application/x-custom"
        attachment = Attachment.from_file(
            file_path=custom_file,
            mime_type=custom_type,
            allowed_mime_types=frozenset({custom_type}),
        )
        assert attachment.mime_type == custom_type


# =============================================================================
# Notifier with Attachments Tests
# =============================================================================


class TestNotifierWithAttachments:
    """Tests for notifier functionality with attachments."""

    def test_notifier_receives_attachments(self, test_app: Engine):
        """Test that notifier with attachments parameter receives them."""
        received_attachments = []

        def notifier_with_attachments(
            _message: str, attachments: list[Attachment] | None = None
        ) -> None:
            received_attachments.append(attachments)

        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(notifier_with_attachments)
        test_app.notify("test message", attachments=[attachment])

        assert len(received_attachments) == 1
        assert received_attachments[0] is not None
        assert len(received_attachments[0]) == 1
        assert received_attachments[0][0].filename == "test.txt"

    def test_legacy_notifier_still_works(self, test_app: Engine):
        """Test that legacy notifier without attachments parameter still works."""
        received_messages = []

        def legacy_notifier(message: str) -> None:
            received_messages.append(message)

        test_app.add_notifier(legacy_notifier)
        test_app.notify("test message")

        assert received_messages == ["test message"]

    def test_legacy_notifier_drops_attachments_silently(self, test_app: Engine):
        """Test that legacy notifier drops attachments silently."""
        received_messages = []

        def legacy_notifier(message: str) -> None:
            received_messages.append(message)

        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(legacy_notifier)

        test_app.notify("test message", attachments=[attachment])

        assert received_messages == ["test message"]

    def test_mixed_notifiers(self, test_app: Engine):
        """Test mixed notifiers - some with attachments, some without."""
        legacy_messages = []
        modern_messages = []
        modern_attachments = []

        def legacy_notifier(message: str) -> None:
            legacy_messages.append(message)

        def modern_notifier(message: str, attachments: list[Attachment] | None = None) -> None:
            modern_messages.append(message)
            modern_attachments.append(attachments)

        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(legacy_notifier)
        test_app.add_notifier(modern_notifier)

        test_app.notify("test message", attachments=[attachment])

        assert legacy_messages == ["test message"]
        assert modern_messages == ["test message"]
        assert modern_attachments[0] is not None
        assert len(modern_attachments[0]) == 1

    def test_notify_with_none_attachments(self, test_app: Engine):
        """Test that None attachments work correctly."""
        received_attachments = []

        def notifier(_message: str, attachments: list[Attachment] | None = None) -> None:
            received_attachments.append(attachments)

        test_app.add_notifier(notifier)
        test_app.notify("test", attachments=None)

        assert received_attachments == [None]

    def test_notify_with_empty_attachments_list(self, test_app: Engine):
        """Test that empty attachments list works correctly."""
        received_attachments = []

        def notifier(_message: str, attachments: list[Attachment] | None = None) -> None:
            received_attachments.append(attachments)

        test_app.add_notifier(notifier)
        test_app.notify("test", attachments=[])

        assert received_attachments == [[]]

    def test_notify_with_multiple_attachments(self, test_app: Engine):
        """Test notifying with multiple attachments."""
        received_attachments = []

        def notifier(_message: str, attachments: list[Attachment] | None = None) -> None:
            received_attachments.append(attachments)

        attachments = [
            Attachment(filename="file1.txt", content=b"one", mime_type="text/plain"),
            Attachment(
                filename="file2.pdf", content=b"%PDF-1.7 content", mime_type="application/pdf"
            ),
            Attachment(
                filename="file3.png", content=b"\x89PNG\r\n\x1a\n data", mime_type="image/png"
            ),
        ]
        test_app.add_notifier(notifier)
        test_app.notify("test", attachments=attachments)

        assert len(received_attachments[0]) == 3
        assert [a.filename for a in received_attachments[0]] == [
            "file1.txt",
            "file2.pdf",
            "file3.png",
        ]

    def test_notifier_error_propagates(self, test_app: Engine):
        """Test that errors from notifiers propagate correctly."""

        def failing_notifier(
            _message: str, attachments: list[Attachment] | None = None
        ) -> None:
            raise RuntimeError("Notifier failed")

        test_app.add_notifier(failing_notifier)

        with pytest.raises(RuntimeError, match="Notifier failed"):
            test_app.notify("test")

    def test_class_based_notifier(self, test_app: Engine):
        """Test that class-based notifiers work correctly."""
        received = []

        class MyNotifier:
            def __call__(self, message: str, attachments: list[Attachment] | None = None) -> None:
                received.append((message, attachments))

        attachment = Attachment(filename="test.txt", content=b"hello", mime_type="text/plain")
        test_app.add_notifier(MyNotifier())
        test_app.notify("test", attachments=[attachment])

        assert len(received) == 1
        assert received[0][0] == "test"
        assert received[0][1] is not None
        assert received[0][1][0].filename == "test.txt"


# =============================================================================
# Notifier Capability Cache Tests
# =============================================================================


class TestNotifierCapabilityCache:
    """Tests for notifier capability caching."""

    def test_cache_avoids_repeated_signature_inspection(self, test_app: Engine):
        """Test that signature inspection is only called once per notifier."""
        from unittest.mock import patch

        def notifier(
            _message: str, attachments: list[Attachment] | None = None
        ) -> None:
            pass

        test_app.add_notifier(notifier)

        with patch("platzky.engine.inspect.signature", wraps=inspect.signature) as mock_sig:
            test_app.notify("test1")
            assert mock_sig.call_count == 1

            test_app.notify("test2")
            assert mock_sig.call_count == 1

            test_app.notify("test3")
            assert mock_sig.call_count == 1

    def test_cache_uses_notifier_id_as_key(self, test_app: Engine):
        """Test that cache uses id(notifier) as key."""

        def notifier(_message: str) -> None:
            pass

        test_app.add_notifier(notifier)
        test_app.notify("test")

        assert id(notifier) in test_app._notifier_capability_cache

    def test_clear_notifier_cache(self, test_app: Engine):
        """Test that clear_notifier_cache clears the cache."""
        from unittest.mock import patch

        def notifier(_message: str) -> None:
            pass

        test_app.add_notifier(notifier)

        with patch("platzky.engine.inspect.signature", wraps=inspect.signature) as mock_sig:
            test_app.notify("test1")
            assert mock_sig.call_count == 1

            test_app.clear_notifier_cache()
            assert len(test_app._notifier_capability_cache) == 0

            test_app.notify("test2")
            assert mock_sig.call_count == 2

    def test_cache_stores_correct_values(self, test_app: Engine):
        """Test that cache stores correct boolean values for different notifiers."""

        def legacy_notifier(_message: str) -> None:
            pass

        def modern_notifier(
            _message: str, attachments: list[Attachment] | None = None
        ) -> None:
            pass

        test_app.add_notifier(legacy_notifier)
        test_app.add_notifier(modern_notifier)
        test_app.notify("test")

        assert test_app._notifier_capability_cache[id(legacy_notifier)] is False
        assert test_app._notifier_capability_cache[id(modern_notifier)] is True

    def test_cache_handles_signature_inspection_errors(
        self, test_app: Engine, caplog: pytest.LogCaptureFixture
    ):
        """Test that signature inspection errors are cached and logged."""
        from unittest.mock import MagicMock, patch

        mock_notifier = MagicMock()
        mock_notifier.__name__ = "mock_notifier"

        test_app.add_notifier(mock_notifier)

        with patch(
            "platzky.engine.inspect.signature", side_effect=ValueError("Cannot inspect")
        ) as mock_sig:
            with caplog.at_level(logging.WARNING):
                test_app.notify("test1")

            assert mock_sig.call_count == 1
            assert "Failed to inspect signature" in caplog.text
            assert "Cannot inspect" in caplog.text

            assert test_app._notifier_capability_cache[id(mock_notifier)] is False

            test_app.notify("test2")
            assert mock_sig.call_count == 1

    def test_different_notifier_instances_have_separate_cache_entries(self, test_app: Engine):
        """Test that different instances of same class have separate cache entries."""

        class MyNotifier:
            def __call__(self, _message: str, attachments: list[Attachment] | None = None) -> None:
                pass

        notifier1 = MyNotifier()
        notifier2 = MyNotifier()

        test_app.add_notifier(notifier1)
        test_app.add_notifier(notifier2)
        test_app.notify("test")

        assert id(notifier1) in test_app._notifier_capability_cache
        assert id(notifier2) in test_app._notifier_capability_cache
        assert id(notifier1) != id(notifier2)

    def test_cache_is_instance_specific(self):
        """Test that cache is instance-specific, not shared across Engine instances."""
        config_data = {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {"TYPE": "json", "DATA": {"site_content": {"pages": []}}},
        }
        config = Config.model_validate(config_data)
        db = Json(config.db)

        engine1 = Engine(config, db, "test1")
        engine2 = Engine(config, db, "test2")

        def notifier(_message: str) -> None:
            pass

        engine1.add_notifier(notifier)
        engine1.notify("test")

        assert id(notifier) in engine1._notifier_capability_cache
        assert id(notifier) not in engine2._notifier_capability_cache


# =============================================================================
# Magic Byte Content Validation Tests
# =============================================================================


class TestMagicByteValidation:
    """Tests for magic byte content validation in Attachment class."""

    PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
    JPEG_MAGIC = b"\xff\xd8\xff"
    GIF87_MAGIC = b"GIF87a"
    GIF89_MAGIC = b"GIF89a"
    PDF_MAGIC = b"%PDF"
    ZIP_MAGIC = b"PK\x03\x04"
    GZIP_MAGIC = b"\x1f\x8b"
    BMP_MAGIC = b"BM"
    TIFF_LE_MAGIC = b"II\x2a\x00"
    TIFF_BE_MAGIC = b"MM\x00\x2a"
    RIFF_MAGIC = b"RIFF"
    OGG_MAGIC = b"OggS"
    MP3_ID3_MAGIC = b"ID3"
    MP3_SYNC_MAGIC = b"\xff\xfb"

    def test_valid_png_content(self):
        """Test that valid PNG content passes validation."""
        content = self.PNG_MAGIC + b"rest of png data"
        attachment = Attachment(
            filename="image.png",
            content=content,
            mime_type="image/png",
        )
        assert attachment.content == content

    def test_valid_jpeg_content(self):
        """Test that valid JPEG content passes validation."""
        content = self.JPEG_MAGIC + b"rest of jpeg data"
        attachment = Attachment(
            filename="image.jpg",
            content=content,
            mime_type="image/jpeg",
        )
        assert attachment.content == content

    def test_valid_gif87a_content(self):
        """Test that valid GIF87a content passes validation."""
        content = self.GIF87_MAGIC + b"rest of gif data"
        attachment = Attachment(
            filename="image.gif",
            content=content,
            mime_type="image/gif",
        )
        assert attachment.content == content

    def test_valid_gif89a_content(self):
        """Test that valid GIF89a content passes validation."""
        content = self.GIF89_MAGIC + b"rest of gif data"
        attachment = Attachment(
            filename="image.gif",
            content=content,
            mime_type="image/gif",
        )
        assert attachment.content == content

    def test_valid_pdf_content(self):
        """Test that valid PDF content passes validation."""
        content = self.PDF_MAGIC + b"-1.7 rest of pdf data"
        attachment = Attachment(
            filename="document.pdf",
            content=content,
            mime_type="application/pdf",
        )
        assert attachment.content == content

    def test_valid_zip_content(self):
        """Test that valid ZIP content passes validation."""
        content = self.ZIP_MAGIC + b"rest of zip data"
        attachment = Attachment(
            filename="archive.zip",
            content=content,
            mime_type="application/zip",
        )
        assert attachment.content == content

    def test_invalid_png_content_raises_error(self):
        """Test that invalid PNG content raises ContentMismatchError."""
        content = b"not a png file"
        with pytest.raises(ContentMismatchError, match="does not match declared MIME type"):
            Attachment(
                filename="image.png",
                content=content,
                mime_type="image/png",
            )

    def test_invalid_pdf_content_raises_error(self):
        """Test that invalid PDF content raises ContentMismatchError."""
        content = b"not a pdf file"
        with pytest.raises(ContentMismatchError, match="does not match declared MIME type"):
            Attachment(
                filename="document.pdf",
                content=content,
                mime_type="application/pdf",
            )

    def test_content_mismatch_error_is_value_error(self):
        """Test that ContentMismatchError is a subclass of ValueError."""
        assert issubclass(ContentMismatchError, ValueError)

    def test_text_mime_types_skip_validation(self):
        """Test that text/* MIME types skip magic byte validation."""
        content = b"Some plain text content"
        attachment = Attachment(
            filename="file.txt",
            content=content,
            mime_type="text/plain",
        )
        assert attachment.content == content

    def test_application_json_skips_validation(self):
        """Test that application/json skips magic byte validation."""
        content = b'{"key": "value"}'
        attachment = Attachment(
            filename="data.json",
            content=content,
            mime_type="application/json",
        )
        assert attachment.content == content

    def test_empty_content_skips_validation(self):
        """Test that empty content skips magic byte validation."""
        attachment = Attachment(
            filename="empty.png",
            content=b"",
            mime_type="image/png",
        )
        assert attachment.content == b""

    def test_validate_content_false_skips_validation(self):
        """Test that validate_content=False skips magic byte validation."""
        content = b"invalid png content"
        attachment = Attachment(
            filename="image.png",
            content=content,
            mime_type="image/png",
            validate_content=False,
        )
        assert attachment.content == content

    def test_magic_bytes_dictionary_exists(self):
        """Test that MAGIC_BYTES dictionary is properly defined."""
        assert isinstance(MAGIC_BYTES, dict)
        assert "image/png" in MAGIC_BYTES
        assert "image/jpeg" in MAGIC_BYTES
        assert "application/pdf" in MAGIC_BYTES

    @pytest.mark.parametrize(
        "mime_type,magic_bytes",
        [
            ("image/png", b"\x89PNG\r\n\x1a\n"),
            ("image/jpeg", b"\xff\xd8\xff"),
            ("image/gif", b"GIF89a"),
            ("application/pdf", b"%PDF"),
            ("application/zip", b"PK\x03\x04"),
            ("application/gzip", b"\x1f\x8b"),
            ("image/bmp", b"BM"),
            ("audio/ogg", b"OggS"),
        ],
    )
    def test_parametrized_valid_magic_bytes(self, mime_type: str, magic_bytes: bytes):
        """Test various MIME types with their correct magic bytes."""
        content = magic_bytes + b"rest of file data"
        attachment = Attachment(
            filename="file.bin",
            content=content,
            mime_type=mime_type,
        )
        assert attachment.content == content

    @pytest.mark.parametrize(
        "mime_type",
        [
            "image/png",
            "image/jpeg",
            "image/gif",
            "application/pdf",
            "application/zip",
        ],
    )
    def test_parametrized_invalid_content_raises_error(self, mime_type: str):
        """Test various MIME types with invalid content."""
        content = b"INVALID CONTENT THAT DOES NOT MATCH ANY MAGIC BYTES"
        with pytest.raises(ContentMismatchError):
            Attachment(
                filename="file.bin",
                content=content,
                mime_type=mime_type,
            )
