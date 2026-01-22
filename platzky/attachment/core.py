"""Core Attachment class factory for file attachments in notifications."""

from __future__ import annotations

import logging
import mimetypes
import ntpath
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from platzky.attachment.constants import (
    AttachmentSizeError,
    BlockedExtensionError,
    ExtensionNotAllowedError,
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

    def __init__(
        self,
        filename: str,
        content: bytes,
        mime_type: str,
        _max_size: int | None = None,
    ) -> None: ...

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


def _guess_mime_type(filename: str) -> str:
    """Guess MIME type from filename, defaulting to application/octet-stream."""
    guessed_type, _ = mimetypes.guess_type(filename)
    return guessed_type or "application/octet-stream"


def _validate_extension(
    filename: str,
    ext: str | None,
    blocked_extensions: frozenset[str],
    allowed_extensions: frozenset[str] | None,
) -> None:
    """Validate filename extension against block-list and allow-list.

    Validation order:
    1. If extension is in blocked_extensions → REJECT (BlockedExtensionError)
    2. If allowed_extensions is None → REJECT (ExtensionNotAllowedError)
    3. If no extension → REJECT (ExtensionNotAllowedError)
    4. If extension not in allowed_extensions → REJECT (ExtensionNotAllowedError)
    5. Otherwise → ALLOW
    """
    if ext is not None and ext in blocked_extensions:
        raise BlockedExtensionError(filename, ext)

    if allowed_extensions is None or ext is None or ext not in allowed_extensions:
        raise ExtensionNotAllowedError(filename, ext)


def _validate_mime_type(mime_type: str, filename: str, allowed_mime_types: frozenset[str]) -> None:
    """Validate MIME type format and against allowlist."""
    if not mime_type or "/" not in mime_type:
        raise ValueError(
            f"Invalid MIME type format '{mime_type}' for attachment '{filename}'. "
            f"MIME type must be in 'type/subtype' format (e.g., 'text/plain', 'image/png')."
        )

    if mime_type not in allowed_mime_types:
        raise ValueError(f"MIME type '{mime_type}' is not allowed for attachment '{filename}'.")


def _do_sanitize_filename(filename: str) -> str:
    """Sanitize filename and return result. Raises if empty after sanitization."""
    sanitized = _sanitize_filename(filename)
    if not sanitized:
        raise ValueError("Attachment filename cannot be empty")
    if sanitized != filename:
        logger.warning(
            "Attachment filename contained path components, sanitized from '%s' to '%s'",
            filename,
            sanitized,
        )
    return sanitized


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
    allowed_extensions = config.allowed_extensions

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
        _max_size: int | None = field(default=None, repr=False, compare=False)

        def __post_init__(self) -> None:
            """Validate attachment data using config from closure."""
            sanitized = _do_sanitize_filename(self.filename)
            if sanitized != self.filename:
                object.__setattr__(self, "filename", sanitized)

            _validate_extension(
                self.filename, _get_extension(self.filename), blocked_extensions, allowed_extensions
            )

            effective_max_size = self._max_size if self._max_size is not None else max_size
            if len(self.content) > effective_max_size:
                raise AttachmentSizeError(self.filename, len(self.content), effective_max_size)

            _validate_mime_type(self.mime_type, self.filename, allowed_mime_types)

            if validate_content:
                validate_content_mime_type(
                    self.content,
                    self.mime_type,
                    self.filename,
                    allow_unrecognized=allow_unrecognized_content,
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
            """
            limit = max_size if max_size_override is None else max_size_override
            if len(content) > limit:
                raise AttachmentSizeError(_sanitize_filename(filename), len(content), limit)
            return cls(filename=filename, content=content, mime_type=mime_type, _max_size=limit)

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
            """
            path = Path(file_path)
            limit = max_size if max_size_override is None else max_size_override

            # Early check to reject obviously oversized files without opening them
            file_size = path.stat().st_size
            if file_size > limit:
                raise AttachmentSizeError(path.name, file_size, limit)

            # Bounded read to prevent TOCTOU: even if file grows after stat(),
            # we never load more than limit + 1 bytes
            with path.open("rb") as f:
                content = f.read(limit + 1)

            if len(content) > limit:
                raise AttachmentSizeError(path.name, len(content), limit)

            effective_filename = filename or path.name
            return cls(
                filename=effective_filename,
                content=content,
                mime_type=mime_type or _guess_mime_type(effective_filename),
                _max_size=limit,
            )

    return Attachment
