"""Core Attachment class factory for file attachments in notifications."""

from __future__ import annotations

import logging
import mimetypes
import ntpath
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from platzky.attachment.constants import AttachmentSizeError
from platzky.attachment.mime_validation import validate_content_mime_type

if TYPE_CHECKING:
    from platzky.config import AttachmentConfig

logger = logging.getLogger(__name__)


def _sanitize_filename(filename: str) -> str:
    """Remove path components from filename, returning just the basename.

    Strips trailing separators first to handle path-only inputs like "/" or "dir/",
    then extracts basename. Returns empty string for invalid inputs rather than
    preserving path separators, allowing validation to reject them.
    """
    # Strip trailing separators to handle inputs like "/" or "dir/"
    stripped = filename.rstrip("/\\")
    return os.path.basename(ntpath.basename(stripped))


def create_attachment_class(config: AttachmentConfig) -> type:
    """Create an Attachment class with configuration captured via closure.

    Args:
        config: Attachment configuration containing allowed_mime_types,
            validate_content, allow_unrecognized_content, and max_size.

    Returns:
        A configured Attachment class that validates attachments according
        to the provided configuration.

    Example:
        >>> from platzky.config import AttachmentConfig
        >>> config = AttachmentConfig()
        >>> Attachment = create_attachment_class(config)
        >>> attachment = Attachment("report.pdf", pdf_bytes, "application/pdf")
    """
    # Capture config values in closure
    allowed_mime_types = config.allowed_mime_types
    validate_content = config.validate_content
    allow_unrecognized_content = config.allow_unrecognized_content
    max_size = config.max_size

    @dataclass(frozen=True)
    class Attachment:
        """Represents a file attachment for notifications.

        Attributes:
            filename: Name of the file (without path components).
            content: Binary content of the file.
            mime_type: MIME type of the file (e.g., 'image/png', 'application/pdf').

        Raises:
            ValueError: If filename is empty or MIME type is invalid/not allowed.
            AttachmentSizeError: If content exceeds configured max_size.
            ContentMismatchError: If content does not match declared MIME type.

        Example:
            >>> attachment = Attachment("report.pdf", pdf_bytes, "application/pdf")
        """

        filename: str
        content: bytes
        mime_type: str

        def __post_init__(self) -> None:
            """Validate attachment data using config from closure."""
            self._sanitize_filename()
            self._validate_size()
            self._validate_mime_type()

            if validate_content:
                validate_content_mime_type(
                    self.content,
                    self.mime_type,
                    self.filename,
                    allow_unrecognized=allow_unrecognized_content,
                )

        def _sanitize_filename(self) -> None:
            """Sanitize filename by removing path components."""
            original_filename = self.filename
            sanitized = _sanitize_filename(original_filename)
            if not sanitized:
                raise ValueError("Attachment filename cannot be empty")
            if sanitized != original_filename:
                object.__setattr__(self, "filename", sanitized)
                logger.warning(
                    "Attachment filename contained path components, sanitized from '%s' to '%s'",
                    original_filename,
                    sanitized,
                )

        def _validate_size(self) -> None:
            """Validate content size against configured max_size."""
            if len(self.content) > max_size:
                raise AttachmentSizeError(self.filename, len(self.content), max_size)

        def _validate_mime_type(self) -> None:
            """Validate MIME type format and against allowlist."""
            if not self.mime_type or "/" not in self.mime_type:
                raise ValueError(
                    f"Invalid MIME type format '{self.mime_type}' for "
                    f"attachment '{self.filename}'. "
                    f"MIME type must be in 'type/subtype' format "
                    f"(e.g., 'text/plain', 'image/png')."
                )

            if self.mime_type not in allowed_mime_types:
                raise ValueError(
                    f"MIME type '{self.mime_type}' is not allowed for "
                    f"attachment '{self.filename}'."
                )

        @classmethod
        def from_bytes(
            cls,
            content: bytes,
            filename: str,
            mime_type: str,
        ) -> "Attachment":
            """Create an Attachment from bytes with size validation before object creation.

            Note: The bytes must already be in memory. This method validates size before
            creating the Attachment object. For memory-safe loading from disk, use from_file().

            Args:
                content: Binary content of the file.
                filename: Name of the file (path components will be stripped).
                mime_type: MIME type of the file (e.g., 'image/png').

            Returns:
                A validated Attachment instance.

            Raises:
                AttachmentSizeError: If content exceeds max_size.
                ValueError: If filename is empty or MIME type is invalid.
            """
            if len(content) > max_size:
                sanitized_filename = _sanitize_filename(filename)
                raise AttachmentSizeError(sanitized_filename, len(content), max_size)

            return cls(
                filename=filename,
                content=content,
                mime_type=mime_type,
            )

        @classmethod
        def from_file(
            cls,
            file_path: str | Path,
            filename: str | None = None,
            mime_type: str | None = None,
        ) -> "Attachment":
            """Create an Attachment from a file path with bounded read for size safety.

            Uses a bounded read to prevent loading oversized files into memory,
            avoiding TOCTOU issues where a file could grow between size check and read.

            Args:
                file_path: Path to the file to read.
                filename: Name to use for the attachment. If None, uses the basename of file_path.
                mime_type: MIME type of the file. If None, guesses from filename.

            Returns:
                A validated Attachment instance.

            Raises:
                AttachmentSizeError: If file size exceeds max_size.
                FileNotFoundError: If the file does not exist.
            """
            path = Path(file_path)

            # Early check to reject obviously oversized files without opening them
            file_size = path.stat().st_size
            if file_size > max_size:
                raise AttachmentSizeError(path.name, file_size, max_size)

            # Bounded read to prevent TOCTOU: even if file grows after stat(),
            # we never load more than max_size + 1 bytes
            with path.open("rb") as f:
                content = f.read(max_size + 1)

            if len(content) > max_size:
                raise AttachmentSizeError(path.name, len(content), max_size)

            effective_filename = filename if filename is not None else path.name
            if mime_type is None:
                guessed_type, _ = mimetypes.guess_type(str(path))
                mime_type = guessed_type or "application/octet-stream"

            return cls(
                filename=effective_filename,
                content=content,
                mime_type=mime_type,
            )

    return Attachment
