"""MIME type validation utilities.

This module provides security-critical validation of file content against
declared MIME types using magic byte signatures. This prevents MIME type
spoofing attacks where malicious content is disguised with innocent MIME types.

Example:
    >>> from platzky.mime_validation import validate_content_mime_type
    >>> validate_content_mime_type(b"\\x89PNG\\r\\n\\x1a\\n...", "image/png", "image.png")
    # Passes silently if valid, raises ContentMismatchError if not
"""

from __future__ import annotations

import logging

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
    "image/svg+xml": [
        b"<?xml", b"<svg", b"\xef\xbb\xbf<?xml", b"\xef\xbb\xbf<svg"
    ],  # With/without BOM
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
    "video/mp4": [
        b"\x00\x00\x00\x14ftyp", b"\x00\x00\x00\x18ftyp",
        b"\x00\x00\x00\x1cftyp", b"\x00\x00\x00\x20ftyp", b"ftyp"
    ],
    "video/webm": [b"\x1a\x45\xdf\xa3"],
    "video/avi": [b"RIFF"],
    "video/ogg": [b"OggS"],
    # Other
    "application/wasm": [b"\x00asm"],
    "application/octet-stream": [],  # Generic binary, no specific signature
}


def validate_content_mime_type(
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
