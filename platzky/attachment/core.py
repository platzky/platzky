"""Core Attachment class for file attachments in notifications."""

from __future__ import annotations

import logging
import mimetypes
import ntpath
import os
from dataclasses import dataclass, field
from pathlib import Path

from platzky.attachment.constants import (
    DEFAULT_MAX_ATTACHMENT_SIZE,
    AttachmentSizeError,
)
from platzky.mime_validation import (
    DEFAULT_ALLOWED_MIME_TYPES,
    validate_content_mime_type,
)

logger = logging.getLogger(__name__)


def _sanitize_filename(filename: str) -> str:
    """Remove path components from filename, returning just the basename."""
    return os.path.basename(ntpath.basename(filename)) or filename


def _format_size_error(filename: str, max_size: int, actual_size: int) -> str:
    """Format a consistent size error message."""
    return (
        f"Attachment '{filename}' exceeds maximum size of "
        f"{max_size / (1024 * 1024):.2f}MB "
        f"(size: {actual_size / (1024 * 1024):.2f}MB)"
    )


@dataclass(frozen=True)
class Attachment:
    """Represents a file attachment for notifications.

    This class provides validated file attachments for the notification system.

    IMPORTANT - Memory Safety:
        The direct constructor (__init__) loads content into memory BEFORE
        validation. When dealing with untrusted input or large files, use the
        factory methods instead:

        - `from_bytes()`: Validates size before creating the Attachment object
        - `from_file()`: Reads files with size checking before loading content

    Attributes:
        filename: Name of the file (without path components).
        content: Binary content of the file.
        mime_type: MIME type of the file (e.g., 'image/png', 'application/pdf').
        max_size: Maximum allowed size in bytes. Defaults to DEFAULT_MAX_ATTACHMENT_SIZE (10MB).
            Can be overridden per-attachment with a custom value.
        allowed_mime_types: Optional set of additional allowed MIME types beyond the defaults.
            If provided, these are added to DEFAULT_ALLOWED_MIME_TYPES.
        validate_content: Whether to validate that content matches the declared MIME type
            using magic bytes (file signatures). Defaults to True.

    Raises:
        ValueError: If filename is empty, content exceeds max size, or MIME type is invalid
            or not in the allowed list.
        AttachmentSizeError: If content exceeds max_size (subclass of ValueError).
        ContentMismatchError: If content does not match declared MIME type (subclass of ValueError).

    Example - Trusted content (already validated or small):
        >>> attachment = Attachment(
        ...     filename="report.pdf",
        ...     content=pdf_bytes,
        ...     mime_type="application/pdf"
        ... )

    Example - Custom size limit:
        >>> attachment = Attachment(
        ...     filename="image.png",
        ...     content=image_bytes,
        ...     mime_type="image/png",
        ...     max_size=5 * 1024 * 1024  # 5MB limit
        ... )

    Example - Untrusted content (use factory methods):
        >>> # From bytes with size validation BEFORE object creation
        >>> attachment = Attachment.from_bytes(
        ...     content=user_uploaded_bytes,
        ...     filename="upload.pdf",
        ...     mime_type="application/pdf",
        ...     max_size=5 * 1024 * 1024  # 5MB limit
        ... )

        >>> # From file path with size checking BEFORE reading
        >>> attachment = Attachment.from_file(
        ...     file_path="/path/to/file.pdf",
        ...     max_size=5 * 1024 * 1024  # 5MB limit
        ... )
    """

    filename: str
    content: bytes
    mime_type: str
    max_size: int = field(default=DEFAULT_MAX_ATTACHMENT_SIZE)
    allowed_mime_types: frozenset[str] | None = field(default=None, repr=False)
    validate_content: bool = field(default=True, repr=False)

    def __post_init__(self) -> None:
        """Validate attachment data.

        Warning:
            This validation occurs AFTER content is already in memory.
            For untrusted input, use from_bytes() or from_file() factory methods
            which validate size BEFORE loading content into memory.
        """
        self._sanitize_filename()
        self._validate_size()
        self._validate_mime_type()

        if self.validate_content:
            validate_content_mime_type(self.content, self.mime_type, self.filename)

    def _sanitize_filename(self) -> None:
        """Sanitize filename by removing path components."""
        original_filename = self.filename
        sanitized = os.path.basename(ntpath.basename(original_filename))
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
        """Validate content size against max_size."""
        if len(self.content) > self.max_size:
            raise AttachmentSizeError(
                f"Attachment '{self.filename}' exceeds maximum size of "
                f"{self.max_size / (1024 * 1024):.2f}MB "
                f"(size: {len(self.content) / (1024 * 1024):.2f}MB)"
            )

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
        max_size: int | None = None,
        allowed_mime_types: frozenset[str] | None = None,
        validate_content: bool = True,
    ) -> Attachment:
        """Create an Attachment from bytes with size validation BEFORE object creation.

        This factory method validates content size before creating the Attachment
        object, preventing memory exhaustion when dealing with untrusted input.

        Use this method when:
        - Processing user-uploaded content
        - Handling data from untrusted sources
        - You want to enforce a custom size limit smaller than the default

        Args:
            content: Binary content of the file.
            filename: Name of the file (path components will be stripped).
            mime_type: MIME type of the file (e.g., 'image/png').
            max_size: Maximum allowed size in bytes. If None, uses
                DEFAULT_MAX_ATTACHMENT_SIZE (10MB). Set to 0 or negative
                to disable size checking (not recommended for untrusted input).
            allowed_mime_types: Optional set of additional allowed MIME types.
            validate_content: Whether to validate content matches MIME type. Defaults to True.

        Returns:
            A validated Attachment instance.

        Raises:
            AttachmentSizeError: If content exceeds max_size.
            ValueError: If filename is empty or MIME type is invalid.

        Example:
            >>> attachment = Attachment.from_bytes(
            ...     content=uploaded_data,
            ...     filename="document.pdf",
            ...     mime_type="application/pdf",
            ...     max_size=5 * 1024 * 1024  # 5MB limit
            ... )
        """
        effective_max_size = max_size if max_size is not None else DEFAULT_MAX_ATTACHMENT_SIZE

        # Validate size BEFORE creating the Attachment object
        if effective_max_size > 0 and len(content) > effective_max_size:
            sanitized_filename = _sanitize_filename(filename)
            raise AttachmentSizeError(
                _format_size_error(sanitized_filename, effective_max_size, len(content))
            )

        return cls(
            filename=filename,
            content=content,
            mime_type=mime_type,
            max_size=effective_max_size,
            allowed_mime_types=allowed_mime_types,
            validate_content=validate_content,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str | Path,
        filename: str | None = None,
        mime_type: str | None = None,
        max_size: int | None = None,
        allowed_mime_types: frozenset[str] | None = None,
        validate_content: bool = True,
    ) -> Attachment:
        """Create an Attachment from a file path with size checking BEFORE reading.

        This factory method checks file size before reading the content into memory,
        preventing memory exhaustion when dealing with potentially large files.

        Use this method when:
        - Reading files from disk where size is unknown
        - Processing files from untrusted sources
        - You want to enforce a custom size limit

        Args:
            file_path: Path to the file to read.
            filename: Name to use for the attachment. If None, uses the
                basename of file_path.
            mime_type: MIME type of the file. If None, attempts to guess
                from the filename using mimetypes module. Falls back to
                'application/octet-stream' if guessing fails.
            max_size: Maximum allowed size in bytes. If None, uses
                DEFAULT_MAX_ATTACHMENT_SIZE (10MB). Set to 0 or negative
                to disable size checking (not recommended for untrusted input).
            allowed_mime_types: Optional set of additional allowed MIME types.
            validate_content: Whether to validate content matches MIME type. Defaults to True.

        Returns:
            A validated Attachment instance.

        Raises:
            AttachmentSizeError: If file size exceeds max_size.
            FileNotFoundError: If the file does not exist.
            PermissionError: If the file cannot be read.
            IsADirectoryError: If the path points to a directory.
            ValueError: If filename is empty or MIME type is invalid.

        Example:
            >>> attachment = Attachment.from_file(
            ...     file_path="/path/to/document.pdf",
            ...     max_size=5 * 1024 * 1024  # 5MB limit
            ... )

            >>> # With custom filename and mime_type
            >>> attachment = Attachment.from_file(
            ...     file_path="/tmp/upload_12345",
            ...     filename="report.pdf",
            ...     mime_type="application/pdf"
            ... )
        """
        path = Path(file_path)
        effective_max_size = max_size if max_size is not None else DEFAULT_MAX_ATTACHMENT_SIZE

        file_size = path.stat().st_size
        if effective_max_size > 0 and file_size > effective_max_size:
            raise AttachmentSizeError(_format_size_error(path.name, effective_max_size, file_size))

        effective_filename = filename if filename is not None else path.name
        effective_mime_type = mime_type
        if effective_mime_type is None:
            guessed_type, _ = mimetypes.guess_type(str(path))
            effective_mime_type = guessed_type or "application/octet-stream"

        return cls(
            filename=effective_filename,
            content=path.read_bytes(),
            mime_type=effective_mime_type,
            max_size=effective_max_size,
            allowed_mime_types=allowed_mime_types,
            validate_content=validate_content,
        )
