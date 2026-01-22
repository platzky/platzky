"""Core Attachment class factory for file attachments in notifications."""

from __future__ import annotations

import logging
import mimetypes
import ntpath
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from platzky.attachment.constants import (
    AttachmentSizeError,
    BlockedExtensionError,
)
from platzky.attachment.mime_validation import validate_content_mime_type

if TYPE_CHECKING:
    from platzky.config import AttachmentConfig

logger = logging.getLogger(__name__)


@runtime_checkable
class AttachmentProtocol(Protocol):
    """Protocol defining the interface for Attachment classes.

    This protocol allows type-safe usage of dynamically created Attachment classes.
    """

    filename: str
    content: bytes
    mime_type: str

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        filename: str,
        mime_type: str,
        max_size_override: int | None = None,
    ) -> "AttachmentProtocol": ...

    @classmethod
    def from_file(
        cls,
        file_path: str | Path,
        filename: str | None = None,
        mime_type: str | None = None,
        max_size_override: int | None = None,
    ) -> "AttachmentProtocol": ...


def _sanitize_filename(filename: str) -> str:
    """Remove path components from filename, returning just the basename.

    Strips trailing separators first to handle path-only inputs like "/" or "dir/",
    then extracts basename. Returns empty string for invalid inputs rather than
    preserving path separators, allowing validation to reject them.
    """
    # Strip trailing separators to handle inputs like "/" or "dir/"
    stripped = filename.rstrip("/\\")
    return os.path.basename(ntpath.basename(stripped))


def _get_extension(filename: str) -> str | None:
    """Extract the file extension from a filename, lowercased.

    Returns None if no extension is found or if extension is empty (e.g., "file.").
    """
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1]
    return ext.lower() or None


def create_attachment_class(config: AttachmentConfig) -> type:
    """Create an Attachment class with configuration captured via closure.

    Args:
        config: Attachment configuration containing allowed_mime_types,
            validate_content, allow_unrecognized_content, max_size,
            and blocked_extensions.

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
    blocked_extensions = config.blocked_extensions

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
            self._validate_extension()
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

        def _validate_extension(self) -> None:
            """Validate filename extension is not in the blocklist."""
            ext = _get_extension(self.filename)
            if ext and ext in blocked_extensions:
                raise BlockedExtensionError(self.filename, ext)

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
            max_size_override: int | None = None,
        ) -> "Attachment":
            """Create an Attachment from bytes with size validation before object creation.

            Note: The bytes must already be in memory. This method validates size before
            creating the Attachment object. For memory-safe loading from disk, use from_file().

            Args:
                content: Binary content of the file.
                filename: Name of the file (path components will be stripped).
                mime_type: MIME type of the file (e.g., 'image/png').
                max_size_override: Optional per-call max size limit.
                    If None, uses configured max_size.

            Returns:
                A validated Attachment instance.

            Raises:
                AttachmentSizeError: If content exceeds max_size.
                ValueError: If filename is empty or MIME type is invalid.
            """
            effective_max_size = max_size_override if max_size_override is not None else max_size
            if len(content) > effective_max_size:
                sanitized_filename = _sanitize_filename(filename)
                raise AttachmentSizeError(sanitized_filename, len(content), effective_max_size)

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
            max_size_override: int | None = None,
        ) -> "Attachment":
            """Create an Attachment from a file path with bounded read for size safety.

            Uses a bounded read to prevent loading oversized files into memory,
            avoiding TOCTOU issues where a file could grow between size check and read.

            Args:
                file_path: Path to the file to read.
                filename: Name to use for the attachment.
                    If None, uses the basename of file_path.
                mime_type: MIME type of the file. If None, guesses from filename.
                max_size_override: Optional per-call max size limit.
                    If None, uses configured max_size.

            Returns:
                A validated Attachment instance.

            Raises:
                AttachmentSizeError: If file size exceeds max_size.
                FileNotFoundError: If the file does not exist.
            """
            path = Path(file_path)
            effective_max_size = max_size_override if max_size_override is not None else max_size

            # Early check to reject obviously oversized files without opening them
            file_size = path.stat().st_size
            if file_size > effective_max_size:
                raise AttachmentSizeError(path.name, file_size, effective_max_size)

            # Bounded read to prevent TOCTOU: even if file grows after stat(),
            # we never load more than max_size + 1 bytes
            with path.open("rb") as f:
                content = f.read(effective_max_size + 1)

            if len(content) > effective_max_size:
                raise AttachmentSizeError(path.name, len(content), effective_max_size)

            effective_filename = filename if filename is not None else path.name
            effective_mime_type = mime_type
            if effective_mime_type is None:
                guessed_type, _ = mimetypes.guess_type(effective_filename)
                effective_mime_type = guessed_type or "application/octet-stream"

            return cls(
                filename=effective_filename,
                content=content,
                mime_type=effective_mime_type,
            )

    return Attachment
