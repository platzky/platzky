"""Attachment package for file attachments in notifications.

This package provides the Attachment class and related utilities for
handling file attachments in the notification system.

# TODO: Consider extracting this package as a standalone PyPI library.
# This module provides unique value not found in existing libraries:
# - Memory-safe factory methods (size validation before loading content)
# - Offset-aware RIFF/MP4 magic byte validation
# - Security-focused MIME type whitelist approach
# - Service-specific size presets (Slack, Discord, Telegram)
# - Zero external dependencies

Example:
    >>> from platzky.attachment import Attachment, SLACK_MAX_SIZE
    >>> attachment = Attachment(
    ...     filename="report.pdf",
    ...     content=pdf_bytes,
    ...     mime_type="application/pdf",
    ...     max_size=SLACK_MAX_SIZE
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
    DISCORD_MAX_SIZE,
    EMAIL_MAX_SIZE,
    SLACK_MAX_SIZE,
    TELEGRAM_MAX_SIZE,
    AttachmentSizeError,
)
from platzky.attachment.core import Attachment

__all__ = [
    "Attachment",
    "AttachmentSizeError",
    "DEFAULT_MAX_ATTACHMENT_SIZE",
    "EMAIL_MAX_SIZE",
    "SLACK_MAX_SIZE",
    "DISCORD_MAX_SIZE",
    "TELEGRAM_MAX_SIZE",
]
