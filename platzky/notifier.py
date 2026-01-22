"""Notification system types and protocols.

This module provides the core types for the platzky notification system:
- Attachment: A validated file attachment for notifications
- Notifier: Protocol defining the notifier interface

Size Limits:
    The default maximum attachment size is 10MB (DEFAULT_MAX_ATTACHMENT_SIZE).
    This default was chosen because 10MB is a common email attachment limit
    used by major email providers (Gmail, Outlook, etc.).

    For different services, you can use the provided presets or specify custom limits:
    - EMAIL_MAX_SIZE (10MB): Standard email attachment limit
    - SLACK_MAX_SIZE (5MB): Slack file upload limit for free plans
    - DISCORD_MAX_SIZE (8MB): Discord file upload limit for non-Nitro users
    - TELEGRAM_MAX_SIZE (50MB): Telegram file upload limit

    Example:
        # Use default (10MB, suitable for email)
        attachment = Attachment(filename="doc.pdf", content=data, mime_type="application/pdf")

        # Use Slack preset
        attachment = Attachment(
            filename="doc.pdf",
            content=data,
            mime_type="application/pdf",
            max_size=SLACK_MAX_SIZE
        )

        # Use custom limit (25MB)
        attachment = Attachment(
            filename="video.mp4",
            content=data,
            mime_type="video/mp4",
            max_size=25 * 1024 * 1024
        )
"""

from __future__ import annotations

import logging
import mimetypes
import ntpath
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

# =============================================================================
# Attachment Size Limits
# =============================================================================
# These constants define common attachment size limits for various services.
# The default (EMAIL_MAX_SIZE) was chosen as it's the most common use case.

# Default maximum attachment size: 10MB (common email attachment limit)
DEFAULT_MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024

# Service-specific size presets
EMAIL_MAX_SIZE = 10 * 1024 * 1024  # 10MB - Gmail, Outlook, most email providers
SLACK_MAX_SIZE = 5 * 1024 * 1024  # 5MB - Slack free plan limit
DISCORD_MAX_SIZE = 8 * 1024 * 1024  # 8MB - Discord non-Nitro limit
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024  # 50MB - Telegram file limit


class AttachmentSizeError(ValueError):
    """Raised when attachment content exceeds the maximum allowed size.

    This is a subclass of ValueError for backwards compatibility with code
    that catches ValueError for size validation failures.
    """

    pass

# Default allowed MIME types - safe, common types for attachments
DEFAULT_ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        # Text types
        "text/plain",
        "text/html",
        "text/csv",
        "text/xml",
        "text/css",
        "text/javascript",
        "text/markdown",
        # Image types
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        "image/bmp",
        "image/tiff",
        # Application types
        "application/pdf",
        "application/json",
        "application/xml",
        "application/zip",
        "application/gzip",
        "application/x-tar",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/rtf",
        # Audio types
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
        # Video types
        "video/mp4",
        "video/webm",
        "video/ogg",
    }
)

# Magic bytes (file signatures) for common MIME types
# Maps MIME type to a list of possible magic byte signatures
MAGIC_BYTES: dict[str, list[bytes]] = {
    # Images
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "image/webp": [b"RIFF"],  # WebP starts with RIFF, full check would include WEBP at offset 8
    "image/bmp": [b"BM"],
    "image/tiff": [b"II\x2a\x00", b"MM\x00\x2a"],  # Little-endian and big-endian TIFF
    "image/x-icon": [b"\x00\x00\x01\x00", b"\x00\x00\x02\x00"],  # ICO and CUR
    "image/svg+xml": [b"<?xml", b"<svg", b"\xef\xbb\xbf<?xml", b"\xef\xbb\xbf<svg"],  # With/without BOM
    # Documents
    "application/pdf": [b"%PDF"],
    "application/zip": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    "application/gzip": [b"\x1f\x8b"],
    "application/x-rar-compressed": [b"Rar!\x1a\x07"],
    "application/x-7z-compressed": [b"7z\xbc\xaf\x27\x1c"],
    # Office formats (all are ZIP-based)
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04"
    ],  # .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
        b"PK\x03\x04"
    ],  # .xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [
        b"PK\x03\x04"
    ],  # .pptx
    # Audio
    "audio/mpeg": [b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2", b"ID3"],  # MP3
    "audio/wav": [b"RIFF"],
    "audio/ogg": [b"OggS"],
    "audio/flac": [b"fLaC"],
    # Video
    "video/mp4": [b"\x00\x00\x00\x14ftyp", b"\x00\x00\x00\x18ftyp", b"\x00\x00\x00\x1cftyp", b"\x00\x00\x00\x20ftyp", b"ftyp"],
    "video/webm": [b"\x1a\x45\xdf\xa3"],
    "video/avi": [b"RIFF"],
    "video/ogg": [b"OggS"],
    # Other
    "application/wasm": [b"\x00asm"],
    "application/octet-stream": [],  # Generic binary, no specific signature
}


class ContentMismatchError(ValueError):
    """Raised when attachment content does not match the declared MIME type.

    This is a subclass of ValueError for backwards compatibility with code
    that catches ValueError for validation failures.
    """

    pass


def _validate_content_matches_mime_type(
    content: bytes, mime_type: str, filename: str
) -> None:
    """Validate that content matches the declared MIME type using magic bytes.

    Args:
        content: The binary content to validate.
        mime_type: The declared MIME type.
        filename: The filename (used for error messages).

    Raises:
        ContentMismatchError: If the content does not match the declared MIME type.
    """
    # Skip validation for empty content
    if not content:
        return

    # Skip validation for text/* MIME types - they don't have reliable magic bytes
    if mime_type.startswith("text/"):
        return

    # Skip validation for application/json and application/xml - text-based formats
    if mime_type in ("application/json", "application/xml", "application/rtf"):
        return

    # Skip validation for MIME types we don't have signatures for
    if mime_type not in MAGIC_BYTES:
        logger.debug(
            "No magic byte signature defined for MIME type '%s', skipping validation for '%s'",
            mime_type,
            filename,
        )
        return

    signatures = MAGIC_BYTES[mime_type]

    # Skip validation if no signatures defined (e.g., application/octet-stream)
    if not signatures:
        return

    # Check if content starts with any of the expected signatures
    for signature in signatures:
        if content.startswith(signature):
            return

    # Content doesn't match any expected signature
    # Get the first few bytes for the error message (hex representation)
    content_preview = content[:16].hex()
    expected_sigs = ", ".join(sig.hex() for sig in signatures)
    raise ContentMismatchError(
        f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
        f"Expected magic bytes: [{expected_sigs}], got: {content_preview}..."
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
            Use service-specific presets like SLACK_MAX_SIZE (5MB), DISCORD_MAX_SIZE (8MB),
            or TELEGRAM_MAX_SIZE (50MB) for different platforms.
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
        ...     max_size=SLACK_MAX_SIZE  # 5MB limit
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
        # Sanitize filename - remove path components (handle both Unix and Windows paths)
        # Use ntpath first to handle Windows paths on any platform, then os.path for Unix
        original_filename = self.filename
        sanitized = os.path.basename(ntpath.basename(original_filename))
        if not sanitized:
            raise ValueError("Attachment filename cannot be empty")
        if sanitized != original_filename:
            # Use object.__setattr__ because dataclass is frozen
            object.__setattr__(self, "filename", sanitized)
            logger.warning(
                "Attachment filename contained path components, sanitized from '%s' to '%s'",
                original_filename,
                sanitized,
            )

        # Validate size against the instance's max_size
        if len(self.content) > self.max_size:
            raise AttachmentSizeError(
                f"Attachment '{self.filename}' exceeds maximum size of "
                f"{self.max_size / (1024 * 1024):.1f}MB "
                f"(size: {len(self.content) / (1024 * 1024):.2f}MB)"
            )

        # Validate MIME type format
        if not self.mime_type or "/" not in self.mime_type:
            raise ValueError(
                f"Invalid MIME type format '{self.mime_type}' for attachment '{self.filename}'. "
                f"MIME type must be in 'type/subtype' format (e.g., 'text/plain', 'image/png')."
            )

        # Validate MIME type against allowlist
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

        # Validate content matches MIME type using magic bytes
        if self.validate_content:
            _validate_content_matches_mime_type(
                self.content, self.mime_type, self.filename
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
        effective_max_size = (
            max_size if max_size is not None else DEFAULT_MAX_ATTACHMENT_SIZE
        )

        # Validate size BEFORE creating the Attachment object
        if effective_max_size > 0 and len(content) > effective_max_size:
            # Sanitize filename for error message
            sanitized_filename = os.path.basename(ntpath.basename(filename)) or filename
            raise AttachmentSizeError(
                f"Attachment '{sanitized_filename}' exceeds maximum size of "
                f"{effective_max_size / (1024 * 1024):.2f}MB "
                f"(size: {len(content) / (1024 * 1024):.2f}MB)"
            )

        return cls(
            filename=filename,
            content=content,
            mime_type=mime_type,
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

        # Check file size BEFORE reading content
        effective_max_size = (
            max_size if max_size is not None else DEFAULT_MAX_ATTACHMENT_SIZE
        )

        file_size = path.stat().st_size
        if effective_max_size > 0 and file_size > effective_max_size:
            raise AttachmentSizeError(
                f"File '{path.name}' exceeds maximum size of "
                f"{effective_max_size / (1024 * 1024):.2f}MB "
                f"(size: {file_size / (1024 * 1024):.2f}MB)"
            )

        # Determine filename
        effective_filename = filename if filename is not None else path.name

        # Determine MIME type
        if mime_type is None:
            guessed_type, _ = mimetypes.guess_type(str(path))
            effective_mime_type = guessed_type or "application/octet-stream"
        else:
            effective_mime_type = mime_type

        # Read file content (size already validated)
        content = path.read_bytes()

        return cls(
            filename=effective_filename,
            content=content,
            mime_type=effective_mime_type,
            allowed_mime_types=allowed_mime_types,
            validate_content=validate_content,
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

    def __call__(self, message: str, attachments: list[Attachment] | None = None) -> None:
        """Send a notification.

        Args:
            message: The notification message text.
            attachments: Optional list of file attachments.
        """
        ...
