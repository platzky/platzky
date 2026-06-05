"""MIME type validation utilities using puremagic for content detection."""

from __future__ import annotations

import puremagic


class ContentMismatchError(ValueError):
    """Raised when attachment content does not match the declared MIME type."""


# puremagic may return alternative names for the same format; normalize to canonical before comparing
_MIME_ALIASES: dict[str, str] = {
    "image/x-ms-bmp": "image/bmp",
    "application/x-gzip": "application/gzip",
    "application/x-zip-compressed": "application/zip",
}

# Text-based formats that don't have reliable magic bytes.
# Note: These types are NOT in the default allowed MIME types for security reasons.
# If users explicitly allow these types, content validation will be skipped.
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

    normalized_declared = _MIME_ALIASES.get(mime_type, mime_type)
    normalized_detected = {_MIME_ALIASES.get(m, m) for m in detected_mimes}
    if normalized_declared in normalized_detected:
        return

    raise ContentMismatchError(
        f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
        f"Detected types: {detected_mimes}"
    )
