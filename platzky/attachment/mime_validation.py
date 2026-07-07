"""MIME type validation utilities using puremagic for content detection."""

from __future__ import annotations

import puremagic


class ContentMismatchError(ValueError):
    """Raised when attachment content does not match the declared MIME type."""


# MIME type equivalences - puremagic may return alternative names for the same format
# Maps canonical types to their aliases
_MIME_EQUIVALENCES: dict[str, set[str]] = {
    "image/bmp": {"image/x-ms-bmp"},
    "application/gzip": {"application/x-gzip"},
    "application/zip": {"application/x-zip-compressed"},
}

# Reverse mapping: alias -> canonical type
_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical for canonical, aliases in _MIME_EQUIVALENCES.items() for alias in aliases
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

    # Direct match
    if mime_type in detected_mimes:
        return

    # Check if declared type is canonical and detected includes an alias
    equivalent_aliases = _MIME_EQUIVALENCES.get(mime_type, set())
    if detected_mimes & equivalent_aliases:
        return

    # Check if declared type is an alias and detected includes the canonical
    canonical = _ALIAS_TO_CANONICAL.get(mime_type)
    if canonical and canonical in detected_mimes:
        return

    raise ContentMismatchError(
        f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
        f"Detected types: {detected_mimes}"
    )
