"""MIME type validation utilities.

This module provides security-critical validation of file content against
declared MIME types using magic byte signatures. This prevents MIME type
spoofing attacks where malicious content is disguised with innocent MIME types.

Example:
    >>> from platzky.attachment.mime_validation import validate_content_mime_type
    >>> validate_content_mime_type(b"\\x89PNG\\r\\n\\x1a\\n...", "image/png", "image.png")
    # Passes silently if valid, raises ContentMismatchError if not
"""

from __future__ import annotations

import logging

import puremagic

logger = logging.getLogger(__name__)


class ContentMismatchError(ValueError):
    """Raised when attachment content does not match the declared MIME type.

    This is a subclass of ValueError for backwards compatibility with code
    that catches ValueError for validation failures.
    """


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

# MIME types that are text-based and should skip validation
# These don't have reliable magic bytes due to their text nature
TEXT_BASED_MIME_TYPES = {
    "application/json",
    "application/xml",
    "application/rtf",
    "image/svg+xml",  # SVG is XML-based, can have whitespace/DOCTYPE/BOM
}

# MIME type equivalences - maps declared types to alternative types that puremagic may return
# This handles cases where the same format has multiple valid MIME types
MIME_TYPE_EQUIVALENCES: dict[str, set[str]] = {
    "image/bmp": {"image/x-ms-bmp"},
    "application/gzip": {"application/x-gzip"},
    "application/zip": {"application/x-zip-compressed"},
}


def validate_content_mime_type(content: bytes, mime_type: str, filename: str) -> None:
    """Validate that content matches the declared MIME type using magic bytes.

    Uses puremagic library for robust file type detection.

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

    # Skip validation for text-based formats (JSON, XML, RTF, SVG)
    if mime_type in TEXT_BASED_MIME_TYPES:
        return

    # Use puremagic to detect the actual content type
    try:
        detected = puremagic.magic_string(content)
    except puremagic.PureError:
        # puremagic couldn't identify the file type
        # Only fail validation for MIME types we know puremagic should be able to detect
        # For custom/unknown types, skip validation
        if mime_type in DEFAULT_ALLOWED_MIME_TYPES:
            raise ContentMismatchError(
                f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
                f"Could not identify file type from content."
            )
        logger.debug(
            "Could not identify file type for '%s' with MIME type '%s', skipping validation",
            filename,
            mime_type,
        )
        return

    # Check if any detected type matches the declared type
    detected_mimes = {m.mime_type for m in detected if m.mime_type}

    # Direct match
    if mime_type in detected_mimes:
        return

    # Check equivalences (e.g., image/bmp == image/x-ms-bmp)
    equivalent_types = MIME_TYPE_EQUIVALENCES.get(mime_type, set())
    if detected_mimes & equivalent_types:
        return

    # Content doesn't match declared MIME type
    raise ContentMismatchError(
        f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
        f"Detected types: {detected_mimes}"
    )
