"""Core Attachment dataclass for file attachments in notifications."""

from __future__ import annotations

import logging
import mimetypes
import ntpath
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from platzky.attachment.constants import (
    AttachmentSizeError,
    BlockedExtensionError,
    ExtensionNotAllowedError,
    InvalidMimeTypeError,
)
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
        raise InvalidMimeTypeError(filename, mime_type, invalid_format=True)

    if mime_type not in allowed_mime_types:
        raise InvalidMimeTypeError(filename, mime_type)


def _do_sanitize_filename(filename: str) -> str:
    """Sanitize filename and return result. Raises if empty or invalid after sanitization."""
    sanitized = _sanitize_filename(filename)
    if not sanitized or sanitized in (".", ".."):
        raise ValueError("Attachment filename cannot be empty")
    if sanitized != filename:
        logger.warning(
            "Attachment filename contained path components, sanitized from '%s' to '%s'",
            filename,
            sanitized,
        )
    return sanitized


@dataclass(frozen=True)
class Attachment:
    """Represents a file attachment for notifications.

    Attributes:
        filename: Name of the file (without path components).
        content: Binary content of the file.
        mime_type: MIME type of the file (e.g., 'image/png', 'application/pdf').

    Example:
        >>> attachment = Attachment.create("report.pdf", pdf_bytes, "application/pdf", config)
    """

    filename: str
    content: bytes
    mime_type: str

    @classmethod
    def create(
        cls,
        filename: str,
        content: bytes,
        mime_type: str,
        config: AttachmentConfig,
    ) -> Attachment:
        """Validate and construct an Attachment.

        Args:
            filename: Name of the file; path components are stripped automatically.
            content: Binary content of the file.
            mime_type: MIME type of the file.
            config: Attachment configuration controlling validation rules.

        Returns:
            A validated, immutable Attachment instance.

        Raises:
            ValueError: If filename is empty after sanitization.
            BlockedExtensionError: If the file extension is on the block-list.
            ExtensionNotAllowedError: If the file extension is not in the allow-list.
            AttachmentSizeError: If content exceeds configured max_size.
            InvalidMimeTypeError: If MIME type is invalid or not in the allowlist.
            ContentMismatchError: If content does not match the declared MIME type.
        """
        return cls._validated(filename, content, mime_type, config, config.max_size)

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        filename: str,
        mime_type: str,
        config: AttachmentConfig,
        max_size_override: int | None = None,
    ) -> Attachment:
        """Create an Attachment from bytes with size validation before object creation.

        Args:
            content: Binary content; must already be in memory.
            filename: Name of the file.
            mime_type: MIME type of the file.
            config: Attachment configuration controlling validation rules.
            max_size_override: Override the config max_size for this attachment only.

        Returns:
            A validated, immutable Attachment instance.
        """
        limit = config.max_size if max_size_override is None else max_size_override
        if len(content) > limit:
            raise AttachmentSizeError(_sanitize_filename(filename), len(content), limit)
        return cls._validated(filename, content, mime_type, config, limit)

    @classmethod
    def from_file(
        cls,
        file_path: str | Path,
        config: AttachmentConfig,
        filename: str | None = None,
        mime_type: str | None = None,
        max_size_override: int | None = None,
    ) -> Attachment:
        """Create an Attachment from a file path with bounded read for size safety.

        Args:
            file_path: Path to the file on disk.
            config: Attachment configuration controlling validation rules.
            filename: Override the filename; defaults to the file's basename.
            mime_type: Override the MIME type; defaults to guessing from filename.
            max_size_override: Override the config max_size for this attachment only.

        Returns:
            A validated, immutable Attachment instance.
        """
        path = Path(file_path)
        limit = config.max_size if max_size_override is None else max_size_override

        # Early check to reject obviously oversized files without opening them
        file_size = path.stat().st_size
        if file_size > limit:
            raise AttachmentSizeError(path.name, file_size, limit)

        # Bounded read to prevent TOCTOU: even if file grows after stat(),
        # we never load more than limit + 1 bytes
        with path.open("rb") as f:
            content = f.read(limit + 1)

        if len(content) > limit:
            # Report actual bytes read (not stat size) for TOCTOU consistency
            raise AttachmentSizeError(path.name, len(content), limit)

        effective_filename = filename or path.name
        return cls._validated(
            effective_filename,
            content,
            mime_type or _guess_mime_type(effective_filename),
            config,
            limit,
        )

    @classmethod
    def _validated(
        cls,
        filename: str,
        content: bytes,
        mime_type: str,
        config: AttachmentConfig,
        max_size: int,
    ) -> Attachment:
        """Run all validation checks with an explicit size limit and construct the instance."""
        sanitized = _do_sanitize_filename(filename)
        _validate_extension(
            sanitized,
            _get_extension(sanitized),
            config.blocked_extensions,
            config.allowed_extensions,
        )
        if len(content) > max_size:
            raise AttachmentSizeError(sanitized, len(content), max_size)
        _validate_mime_type(mime_type, sanitized, config.allowed_mime_types)
        if config.validate_content:
            validate_content_mime_type(
                content,
                mime_type,
                sanitized,
                allow_unrecognized=config.allow_unrecognized_content,
            )
        return cls(filename=sanitized, content=content, mime_type=mime_type)
