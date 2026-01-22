"""Notification system types and protocols.

This module provides the Notifier protocol for the platzky notification system.

For the Attachment class and related utilities, see platzky.attachment module.

For backward compatibility, this module re-exports all symbols from the attachment module.
New code should import directly from platzky.attachment for clarity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

# =============================================================================
# Backward Compatibility Re-exports
# =============================================================================
# These re-exports ensure existing code continues to work:
#   from platzky.notifier import Attachment, MAGIC_BYTES, etc.
#
# New code should import from platzky.attachment:
#   from platzky.attachment import Attachment, MAGIC_BYTES
from platzky.attachment import (
    DEFAULT_ALLOWED_MIME_TYPES as DEFAULT_ALLOWED_MIME_TYPES,
)
from platzky.attachment import (
    MAGIC_BYTES as MAGIC_BYTES,
)
from platzky.attachment import (
    MAX_ATTACHMENT_SIZE as MAX_ATTACHMENT_SIZE,
)
from platzky.attachment import (
    Attachment as Attachment,
)
from platzky.attachment import (
    AttachmentSizeError as AttachmentSizeError,
)
from platzky.attachment import (
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
