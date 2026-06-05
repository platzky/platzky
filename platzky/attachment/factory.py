"""Factory function for creating validated Attachment instances."""

from __future__ import annotations

from pathlib import PureWindowsPath
from typing import TYPE_CHECKING

from werkzeug.utils import secure_filename

from platzky.attachment.attachment import Attachment
from platzky.attachment.constants import (
    AttachmentSizeError,
    BlockedExtensionError,
    ExtensionNotAllowedError,
    InvalidMimeTypeError,
)
from platzky.attachment.mime_validation import validate_content_mime_type

if TYPE_CHECKING:
    from platzky.config import AttachmentConfig


def create_attachment(
    filename: str, content: bytes, mime_type: str, config: AttachmentConfig
) -> Attachment:
    """Validate inputs and construct an Attachment.

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
    # PureWindowsPath handles both / and \ separators cross-platform
    sanitized = secure_filename(PureWindowsPath(filename).name)
    if not sanitized:
        raise ValueError("Attachment filename cannot be empty")

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

    return Attachment(filename=sanitized, content=content, mime_type=mime_type)
