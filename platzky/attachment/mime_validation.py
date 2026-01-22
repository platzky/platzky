"""MIME type validation utilities using puremagic for content detection."""

from __future__ import annotations

import puremagic


class ContentMismatchError(ValueError):
    """Raised when attachment content does not match the declared MIME type."""


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

# MIME type equivalences - puremagic may return alternative names for the same format
_MIME_EQUIVALENCES: dict[str, set[str]] = {
    "image/bmp": {"image/x-ms-bmp"},
    "application/gzip": {"application/x-gzip"},
    "application/zip": {"application/x-zip-compressed"},
}

# Text-based formats that don't have reliable magic bytes
_SKIP_VALIDATION_TYPES = {"application/json", "application/xml", "application/rtf", "image/svg+xml"}


def validate_content_mime_type(
    content: bytes,
    mime_type: str,
    filename: str,
    *,
    allow_unrecognized: bool = False,
) -> None:
    """Validate that content matches the declared MIME type using magic bytes.

    Args:
        content: The binary content to validate.
        mime_type: The declared MIME type.
        filename: The filename (used for error messages).
        allow_unrecognized: If True, allow content that cannot be identified.

    Raises:
        ContentMismatchError: If content does not match the declared MIME type.
    """
    # Skip validation for empty content, text types, and text-based formats
    if not content or mime_type.startswith("text/") or mime_type in _SKIP_VALIDATION_TYPES:
        return

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
    equivalent_types = _MIME_EQUIVALENCES.get(mime_type, set())

    if mime_type in detected_mimes or (detected_mimes & equivalent_types):
        return

    raise ContentMismatchError(
        f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
        f"Detected types: {detected_mimes}"
    )
