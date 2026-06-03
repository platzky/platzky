"""Attachment package for file attachments in notifications.

Usage via Engine (recommended):
    >>> attachment = engine.create_attachment("report.pdf", pdf_bytes, "application/pdf")

Direct usage with explicit config:
    >>> from platzky.attachment import Attachment
    >>> from platzky.config import AttachmentConfig
    >>> config = AttachmentConfig(max_size=5 * 1024 * 1024)  # 5MB limit
    >>> attachment = Attachment.create("report.pdf", pdf_bytes, "application/pdf", config)
"""

from platzky.attachment.constants import (
    BLOCKED_EXTENSIONS,
    DEFAULT_MAX_ATTACHMENT_SIZE,
    AttachmentSizeError,
    BlockedExtensionError,
    ExtensionNotAllowedError,
    InvalidMimeTypeError,
)
from platzky.attachment.core import Attachment
from platzky.attachment.mime_validation import ContentMismatchError

__all__ = [
    "BLOCKED_EXTENSIONS",
    "DEFAULT_MAX_ATTACHMENT_SIZE",
    "Attachment",
    "AttachmentSizeError",
    "BlockedExtensionError",
    "ContentMismatchError",
    "ExtensionNotAllowedError",
    "InvalidMimeTypeError",
]
