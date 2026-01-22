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

import puremagic


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


def validate_content_mime_type(
    content: bytes,
    mime_type: str,
    filename: str,
    *,
    allow_unrecognized: bool = False,
) -> None:
    """Validate that content matches the declared MIME type using magic bytes.

    Uses puremagic library for robust file type detection.

    Args:
        content: The binary content to validate.
        mime_type: The declared MIME type.
        filename: The filename (used for error messages).
        allow_unrecognized: If True, skip validation when content type cannot be
            detected. If False (default), raise an error for unrecognized content.

    Raises:
        ContentMismatchError: If the content does not match the declared MIME type,
            or if content cannot be identified and allow_unrecognized is False.
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
    except puremagic.PureError as err:
        if allow_unrecognized:
            return
        raise ContentMismatchError(
            f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
            "Could not identify file type from content."
        ) from err

    detected_mimes = {m.mime_type for m in detected if m.mime_type}
    equivalent_types = MIME_TYPE_EQUIVALENCES.get(mime_type, set())

    if mime_type in detected_mimes or (detected_mimes & equivalent_types):
        return

    raise ContentMismatchError(
        f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
        f"Detected types: {detected_mimes}"
    )
