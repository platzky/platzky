"""Attachment package for file attachments in notifications.

This package provides the Attachment class and related utilities for
handling file attachments in the notification system.

Example:
    >>> from platzky.attachment import Attachment, DEFAULT_MAX_ATTACHMENT_SIZE
    >>> attachment = Attachment(
    ...     filename="report.pdf",
    ...     content=pdf_bytes,
    ...     mime_type="application/pdf",
    ...     max_size=5 * 1024 * 1024  # Custom 5MB limit
    ... )

For untrusted input, use factory methods:
    >>> attachment = Attachment.from_bytes(
    ...     content=user_data,
    ...     filename="upload.pdf",
    ...     mime_type="application/pdf"
    ... )
"""

from platzky.attachment.constants import (
    DEFAULT_MAX_ATTACHMENT_SIZE,
    AttachmentSizeError,
)
from platzky.attachment.core import Attachment
from platzky.attachment.mime_validation import (
    DEFAULT_ALLOWED_MIME_TYPES,
    MAGIC_BYTES,
    ContentMismatchError,
    validate_content_mime_type,
)
