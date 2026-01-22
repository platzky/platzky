"""Notification system types and protocols.

This module provides the core types for the platzky notification system:
- Attachment: A validated file attachment for notifications
- Notifier: Protocol defining the notifier interface
"""

import logging
import ntpath
import os
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

# Default maximum attachment size: 10MB
DEFAULT_MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024


@dataclass(frozen=True)
class Attachment:
    """Represents a file attachment for notifications.

    Attributes:
        filename: Name of the file (without path components).
        content: Binary content of the file.
        mime_type: MIME type of the file (e.g., 'image/png', 'application/pdf').

    Raises:
        ValueError: If filename is empty, content exceeds max size, or MIME type is invalid.
    """

    filename: str
    content: bytes
    mime_type: str

    def __post_init__(self) -> None:
        """Validate attachment data."""
        # Sanitize filename - remove path components (handle both Unix and Windows paths)
        # Use ntpath first to handle Windows paths on any platform, then os.path for Unix
        sanitized = os.path.basename(ntpath.basename(self.filename))
        if not sanitized:
            raise ValueError("Attachment filename cannot be empty")
        if sanitized != self.filename:
            # Use object.__setattr__ because dataclass is frozen
            object.__setattr__(self, "filename", sanitized)
            logger.warning(
                "Attachment filename contained path components, sanitized from '%s' to '%s'",
                self.filename,
                sanitized,
            )

        # Validate size
        if len(self.content) > DEFAULT_MAX_ATTACHMENT_SIZE:
            raise ValueError(
                f"Attachment '{self.filename}' exceeds maximum size of "
                f"{DEFAULT_MAX_ATTACHMENT_SIZE / (1024 * 1024):.0f}MB "
                f"(size: {len(self.content) / (1024 * 1024):.2f}MB)"
            )

        # Basic MIME type validation
        if not self.mime_type or "/" not in self.mime_type:
            raise ValueError(
                f"Invalid MIME type '{self.mime_type}' for attachment '{self.filename}'"
            )


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

    def __call__(
        self, message: str, attachments: list[Attachment] | None = None
    ) -> None:
        """Send a notification.

        Args:
            message: The notification message text.
            attachments: Optional list of file attachments.
        """
        ...
