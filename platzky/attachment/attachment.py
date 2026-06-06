"""Attachment dataclass for file attachments in notifications."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Attachment:
    """Represents a file attachment for notifications.

    Attributes:
        filename: Name of the file (without path components).
        content: Binary content of the file.
        mime_type: MIME type of the file (e.g., 'image/png', 'application/pdf').
    """

    filename: str
    content: bytes
    mime_type: str
