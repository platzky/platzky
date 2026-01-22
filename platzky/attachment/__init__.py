"""Attachment package for file attachments in notifications.

This package provides the Attachment class and related utilities for
handling file attachments in the notification system.

Example:
    >>> from platzky.attachment import Attachment, MAX_ATTACHMENT_SIZE
    >>> attachment = Attachment(
    ...     filename="report.pdf",
    ...     content=pdf_bytes,
    ...     mime_type="application/pdf",
    ... )

For untrusted input, use factory methods:
    >>> attachment = Attachment.from_bytes(
    ...     content=user_data,
    ...     filename="upload.pdf",
    ...     mime_type="application/pdf"
    ... )
"""

from platzky.attachment.constants import (
    MAX_ATTACHMENT_SIZE as MAX_ATTACHMENT_SIZE,
)
from platzky.attachment.constants import (
    AttachmentSizeError as AttachmentSizeError,
)
from platzky.attachment.core import Attachment as Attachment
from platzky.attachment.mime_validation import (
    DEFAULT_ALLOWED_MIME_TYPES as DEFAULT_ALLOWED_MIME_TYPES,
)
from platzky.attachment.mime_validation import (
    MAGIC_BYTES as MAGIC_BYTES,
)
from platzky.attachment.mime_validation import (
    ContentMismatchError as ContentMismatchError,
)
from platzky.attachment.mime_validation import (
    validate_content_mime_type as validate_content_mime_type,
)
