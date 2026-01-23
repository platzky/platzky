"""Attachment package for file attachments in notifications.

This package provides the Attachment class factory and related utilities for
handling file attachments in the notification system.

Usage via Engine (recommended):
    >>> # Engine exposes a configured Attachment class
    >>> attachment = engine.Attachment("report.pdf", pdf_bytes, "application/pdf")

Direct usage with factory:
    >>> from platzky.attachment import create_attachment_class
    >>> from platzky.config import AttachmentConfig
    >>> config = AttachmentConfig(max_size=5 * 1024 * 1024)  # 5MB limit
    >>> Attachment = create_attachment_class(config)
    >>> attachment = Attachment("report.pdf", pdf_bytes, "application/pdf")
"""

from platzky.attachment.constants import (
    BLOCKED_EXTENSIONS,
    DEFAULT_MAX_ATTACHMENT_SIZE,
    AttachmentSizeError,
    BlockedExtensionError,
    ExtensionNotAllowedError,
    InvalidMimeTypeError,
)
from platzky.attachment.core import AttachmentProtocol, create_attachment_class
from platzky.attachment.mime_validation import ContentMismatchError

__all__ = [
    "BLOCKED_EXTENSIONS",
    "DEFAULT_MAX_ATTACHMENT_SIZE",
    "AttachmentProtocol",
    "AttachmentSizeError",
    "BlockedExtensionError",
    "ContentMismatchError",
    "ExtensionNotAllowedError",
    "InvalidMimeTypeError",
    "create_attachment_class",
]
