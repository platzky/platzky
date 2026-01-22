"""Core Attachment class for file attachments in notifications."""

from __future__ import annotations

import logging
import mimetypes
import ntpath
import os
from dataclasses import dataclass, field
from pathlib import Path

from platzky.attachment.constants import (
    MAX_ATTACHMENT_SIZE,
    AttachmentSizeError,
)
from platzky.attachment.mime_validation import (
    DEFAULT_ALLOWED_MIME_TYPES,
    validate_content_mime_type,
)

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


@dataclass(frozen=True)
class Attachment:
    """Represents a file attachment for notifications.

    Attributes:
        filename: Name of the file (without path components).
        content: Binary content of the file.
        mime_type: MIME type of the file (e.g., 'image/png', 'application/pdf').
        allowed_mime_types: Optional set of additional allowed MIME types beyond the defaults.
        validate_content: Whether to validate that content matches the declared MIME type.
        allow_unrecognized_content: If True, allow content that cannot be identified.
            If False (default), reject unrecognized content for security.

    Raises:
        ValueError: If filename is empty or MIME type is invalid/not allowed.
        AttachmentSizeError: If content exceeds MAX_ATTACHMENT_SIZE.
        ContentMismatchError: If content does not match declared MIME type.

    Example:
        >>> attachment = Attachment(
        ...     filename="report.pdf",
        ...     content=pdf_bytes,
        ...     mime_type="application/pdf"
        ... )
    """

    filename: str
    content: bytes
    mime_type: str
    allowed_mime_types: frozenset[str] | None = field(default=None, repr=False)
    validate_content: bool = field(default=True, repr=False)
    allow_unrecognized_content: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        """Validate attachment data."""
        self._sanitize_filename()
        self._validate_size()
        self._validate_mime_type()

        if self.validate_content:
            validate_content_mime_type(
                self.content,
                self.mime_type,
                self.filename,
                allow_unrecognized=self.allow_unrecognized_content,
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
        """Validate content size against MAX_ATTACHMENT_SIZE."""
        if len(self.content) > MAX_ATTACHMENT_SIZE:
            raise AttachmentSizeError(self.filename, len(self.content))

    def _validate_mime_type(self) -> None:
        """Validate MIME type format and against allowlist."""
        if not self.mime_type or "/" not in self.mime_type:
            raise ValueError(
                f"Invalid MIME type format '{self.mime_type}' for attachment '{self.filename}'. "
                f"MIME type must be in 'type/subtype' format (e.g., 'text/plain', 'image/png')."
            )

        effective_allowed_types = DEFAULT_ALLOWED_MIME_TYPES
        if self.allowed_mime_types:
            effective_allowed_types = DEFAULT_ALLOWED_MIME_TYPES | self.allowed_mime_types

        if self.mime_type not in effective_allowed_types:
            raise ValueError(
                f"MIME type '{self.mime_type}' is not allowed for attachment '{self.filename}'. "
                f"Allowed types include: text/plain, text/html, image/png, image/jpeg, "
                f"application/pdf, application/json, and others. "
                f"Use 'allowed_mime_types' parameter to extend the allowed list if needed."
            )

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        filename: str,
        mime_type: str,
        allowed_mime_types: frozenset[str] | None = None,
        validate_content: bool = True,
        allow_unrecognized_content: bool = False,
    ) -> Attachment:
        """Create an Attachment from bytes with size validation before object creation.

        Note: The bytes must already be in memory. This method validates size before
        creating the Attachment object. For memory-safe loading from disk, use from_file().

        Args:
            content: Binary content of the file.
            filename: Name of the file (path components will be stripped).
            mime_type: MIME type of the file (e.g., 'image/png').
            allowed_mime_types: Optional set of additional allowed MIME types.
            validate_content: Whether to validate content matches MIME type.
            allow_unrecognized_content: If True, allow content that cannot be identified.

        Returns:
            A validated Attachment instance.

        Raises:
            AttachmentSizeError: If content exceeds MAX_ATTACHMENT_SIZE.
            ValueError: If filename is empty or MIME type is invalid.
        """
        if len(content) > MAX_ATTACHMENT_SIZE:
            sanitized_filename = _sanitize_filename(filename)
            raise AttachmentSizeError(sanitized_filename, len(content))

        return cls(
            filename=filename,
            content=content,
            mime_type=mime_type,
            allowed_mime_types=allowed_mime_types,
            validate_content=validate_content,
            allow_unrecognized_content=allow_unrecognized_content,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str | Path,
        filename: str | None = None,
        mime_type: str | None = None,
        allowed_mime_types: frozenset[str] | None = None,
        validate_content: bool = True,
        allow_unrecognized_content: bool = False,
    ) -> Attachment:
        """Create an Attachment from a file path with bounded read for size safety.

        Uses a bounded read to prevent loading oversized files into memory,
        avoiding TOCTOU issues where a file could grow between size check and read.

        Args:
            file_path: Path to the file to read.
            filename: Name to use for the attachment. If None, uses the basename of file_path.
            mime_type: MIME type of the file. If None, guesses from filename.
            allowed_mime_types: Optional set of additional allowed MIME types.
            validate_content: Whether to validate content matches MIME type.
            allow_unrecognized_content: If True, allow content that cannot be identified.

        Returns:
            A validated Attachment instance.

        Raises:
            AttachmentSizeError: If file size exceeds MAX_ATTACHMENT_SIZE.
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path)

        # Early check to reject obviously oversized files without opening them
        file_size = path.stat().st_size
        if file_size > MAX_ATTACHMENT_SIZE:
            raise AttachmentSizeError(path.name, file_size)

        # Bounded read to prevent TOCTOU: even if file grows after stat(),
        # we never load more than MAX_ATTACHMENT_SIZE + 1 bytes
        with path.open("rb") as f:
            content = f.read(MAX_ATTACHMENT_SIZE + 1)

        if len(content) > MAX_ATTACHMENT_SIZE:
            raise AttachmentSizeError(path.name, len(content))

        effective_filename = filename if filename is not None else path.name
        effective_mime_type = mime_type
        if effective_mime_type is None:
            guessed_type, _ = mimetypes.guess_type(str(path))
            effective_mime_type = guessed_type or "application/octet-stream"

        return cls(
            filename=effective_filename,
            content=content,
            mime_type=effective_mime_type,
            allowed_mime_types=allowed_mime_types,
            validate_content=validate_content,
            allow_unrecognized_content=allow_unrecognized_content,
        )
