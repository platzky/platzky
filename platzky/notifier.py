"""Notification system types and protocols.

This module provides the Notifier protocol for the platzky notification system.

For the Attachment class and related utilities, see:
- platzky.attachment: Attachment class, size limits, AttachmentSizeError
- platzky.mime_validation: MIME type validation, magic bytes, ContentMismatchError

For backward compatibility, this module re-exports all symbols from the above modules.
New code should import directly from the specific modules for clarity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

# =============================================================================
# Backward Compatibility Re-exports
# =============================================================================
# These re-exports ensure existing code continues to work:
#   from platzky.notifier import Attachment, MAGIC_BYTES, etc.
#
# New code should import from the specific modules:
#   from platzky.attachment import Attachment
#   from platzky.mime_validation import MAGIC_BYTES
from platzky.attachment import (
    DEFAULT_MAX_ATTACHMENT_SIZE as DEFAULT_MAX_ATTACHMENT_SIZE,
)
from platzky.attachment import (
    Attachment as Attachment,
)
from platzky.attachment import (
    AttachmentSizeError as AttachmentSizeError,
)
from platzky.mime_validation import (
    DEFAULT_ALLOWED_MIME_TYPES as DEFAULT_ALLOWED_MIME_TYPES,
)
from platzky.mime_validation import (
    MAGIC_BYTES as MAGIC_BYTES,
)
from platzky.mime_validation import (
    ContentMismatchError as ContentMismatchError,
)

if TYPE_CHECKING:
    from platzky.attachment import Attachment


class Notifier(Protocol):
    """Protocol for notification handlers.

    Notifiers receive messages and optional attachments. They should handle
    the actual delivery mechanism (email, Slack, webhook, etc.).

    Example:
        class EmailNotifier:
            def __call__(
                self, message: str, attachments: list[Attachment] | None = None
            ) -> None:
                # Send email with message and attachments
                ...

        engine.add_notifier(EmailNotifier())
    """

    def __call__(self, message: str, attachments: list[Attachment] | None = None) -> None:
        """Send a notification.

        Args:
            message: The notification message text.
            attachments: Optional list of file attachments.
        """
        ...
