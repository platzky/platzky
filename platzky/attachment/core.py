"""Core Attachment dataclass for file attachments in notifications."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING

from werkzeug.utils import secure_filename

from platzky.attachment.constants import (
    AttachmentSizeError,
    BlockedExtensionError,
    ExtensionNotAllowedError,
    InvalidMimeTypeError,
)
from platzky.attachment.mime_validation import validate_content_mime_type

if TYPE_CHECKING:
    from platzky.config import AttachmentConfig


def _sanitize(filename: str) -> str:
    """Strip path components and sanitize filename. Raises if result is empty."""
    # PureWindowsPath handles both / and \ separators cross-platform
    sanitized = secure_filename(PureWindowsPath(filename).name)
    if not sanitized:
        raise ValueError("Attachment filename cannot be empty")
    return sanitized


@dataclass(frozen=True)
class Attachment:
    """Represents a file attachment for notifications.

    Attributes:
        filename: Name of the file (without path components).
        content: Binary content of the file.
        mime_type: MIME type of the file (e.g., 'image/png', 'application/pdf').

    Example:
        >>> attachment = Attachment.create("report.pdf", pdf_bytes, "application/pdf", config)
    """

    filename: str
    content: bytes
    mime_type: str

    @classmethod
    def create(
        cls,
        filename: str,
        content: bytes,
        mime_type: str,
        config: AttachmentConfig,
    ) -> Attachment:
        """Validate and construct an Attachment.

        Args:
            filename: Name of the file; path components are stripped automatically.
            content: Binary content of the file.
            mime_type: MIME type of the file.
            config: Attachment configuration controlling validation rules.

        Returns:
            A validated, immutable Attachment instance.

        Raises:
            ValueError: If filename is empty after sanitization.
            BlockedExtensionError: If the file extension is on the block-list.
            ExtensionNotAllowedError: If the file extension is not in the allow-list.
            AttachmentSizeError: If content exceeds configured max_size.
            InvalidMimeTypeError: If MIME type is invalid or not in the allowlist.
            ContentMismatchError: If content does not match the declared MIME type.
        """
        sanitized = _sanitize(filename)

        ext = sanitized.rsplit(".", 1)[-1].lower() if "." in sanitized else None
        if ext is not None and ext in config.blocked_extensions:
            raise BlockedExtensionError(sanitized, ext)
        if config.allowed_extensions is None or ext is None or ext not in config.allowed_extensions:
            raise ExtensionNotAllowedError(sanitized, ext)

        if len(content) > config.max_size:
            raise AttachmentSizeError(sanitized, len(content), config.max_size)

        if not mime_type or "/" not in mime_type:
            raise InvalidMimeTypeError(sanitized, mime_type, invalid_format=True)
        if mime_type not in config.allowed_mime_types:
            raise InvalidMimeTypeError(sanitized, mime_type)

        if config.validate_content:
            validate_content_mime_type(
                content, mime_type, sanitized, allow_unrecognized=config.allow_unrecognized_content
            )

        return cls(filename=sanitized, content=content, mime_type=mime_type)

    @classmethod
    def from_file(
        cls,
        file_path: str | Path,
        config: AttachmentConfig,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> Attachment:
        """Create an Attachment from a file path with bounded read for size safety.

        Args:
            file_path: Path to the file on disk.
            config: Attachment configuration controlling validation rules.
            filename: Override the filename; defaults to the file's basename.
            mime_type: Override the MIME type; defaults to guessing from filename.

        Returns:
            A validated, immutable Attachment instance.
        """
        path = Path(file_path)

        # Early check to reject obviously oversized files without opening them
        file_size = path.stat().st_size
        if file_size > config.max_size:
            raise AttachmentSizeError(path.name, file_size, config.max_size)

        # Bounded read to prevent TOCTOU: even if file grows after stat(),
        # we never load more than max_size + 1 bytes
        with path.open("rb") as f:
            content = f.read(config.max_size + 1)

        if len(content) > config.max_size:
            raise AttachmentSizeError(path.name, len(content), config.max_size)

        effective_filename = filename or path.name
        effective_mime = (
            mime_type or mimetypes.guess_type(effective_filename)[0] or "application/octet-stream"
        )
        return cls.create(effective_filename, content, effective_mime, config)
