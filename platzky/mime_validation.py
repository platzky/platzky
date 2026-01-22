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
# Note: RIFF-based formats and MP4 use special validation functions below
MAGIC_BYTES: dict[str, list[bytes]] = {
    # Images
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "image/bmp": [b"BM"],
    "image/tiff": [b"II\x2a\x00", b"MM\x00\x2a"],  # Little-endian and big-endian TIFF
    "image/x-icon": [b"\x00\x00\x01\x00", b"\x00\x00\x02\x00"],  # ICO and CUR
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
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [b"PK\x03\x04"],  # .xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [
        b"PK\x03\x04"
    ],  # .pptx
    # Audio
    "audio/mpeg": [b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2", b"ID3"],  # MP3
    "audio/ogg": [b"OggS"],
    "audio/flac": [b"fLaC"],
    # Video
    "video/webm": [b"\x1a\x45\xdf\xa3"],
    "video/ogg": [b"OggS"],
    # Other
    "application/wasm": [b"\x00asm"],
    "application/octet-stream": [],  # Generic binary, no specific signature
}

# MIME types that require special offset-aware validation
# These are handled by dedicated validation functions
MIME_TYPES_WITH_SPECIAL_VALIDATION = {
    # RIFF-based formats: RIFF header + format tag at offset 8
    "image/webp",  # RIFF....WEBP
    "audio/wav",  # RIFF....WAVE
    "video/avi",  # RIFF....AVI
    # MP4/QuickTime: ftyp box with variable size
    "video/mp4",
}

# MIME types that are text-based and should skip validation
# These don't have reliable magic bytes due to their text nature
TEXT_BASED_MIME_TYPES = {
    "application/json",
    "application/xml",
    "application/rtf",
    "image/svg+xml",  # SVG is XML-based, can have whitespace/DOCTYPE/BOM
}


def _validate_riff_format(content: bytes, expected_format: bytes) -> bool:
    """Validate RIFF-based format with offset-aware check.

    RIFF files have structure: RIFF + 4-byte size + format tag (4 bytes at offset 8)

    Args:
        content: The binary content to validate.
        expected_format: The expected format tag (e.g., b"WEBP", b"WAVE", b"AVI ")

    Returns:
        True if content is valid RIFF with expected format, False otherwise.
    """
    if len(content) < 12:
        return False
    # Check RIFF header and format tag at offset 8
    return content[:4] == b"RIFF" and content[8:12] == expected_format


def _validate_mp4(content: bytes) -> bool:
    """Validate MP4/QuickTime format with proper ftyp box detection.

    MP4 files have an ftyp box with structure:
    - 4 bytes: box size (big-endian)
    - 4 bytes: box type ("ftyp")
    - The ftyp box is typically at the start but box size varies

    Args:
        content: The binary content to validate.

    Returns:
        True if content appears to be valid MP4, False otherwise.
    """
    if len(content) < 8:
        return False

    # Check for ftyp at offset 4 (after the 4-byte size)
    if content[4:8] == b"ftyp":
        return True

    # Some MP4 files may have ftyp at different positions, but typically it's at start
    # Check first 32 bytes for ftyp box
    return b"ftyp" in content[:32]


def validate_content_mime_type(content: bytes, mime_type: str, filename: str) -> None:
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

    # Skip validation for text-based formats (JSON, XML, RTF, SVG)
    if mime_type in TEXT_BASED_MIME_TYPES:
        return

    # Handle RIFF-based formats with offset-aware validation
    if mime_type == "image/webp":
        if _validate_riff_format(content, b"WEBP"):
            return
        raise ContentMismatchError(
            f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
            f"Expected RIFF/WEBP format, got: {content[:12].hex()}..."
        )

    if mime_type == "audio/wav":
        if _validate_riff_format(content, b"WAVE"):
            return
        raise ContentMismatchError(
            f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
            f"Expected RIFF/WAVE format, got: {content[:12].hex()}..."
        )

    if mime_type == "video/avi":
        if _validate_riff_format(content, b"AVI "):
            return
        raise ContentMismatchError(
            f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
            f"Expected RIFF/AVI format, got: {content[:12].hex()}..."
        )

    # Handle MP4 with proper ftyp box detection
    if mime_type == "video/mp4":
        if _validate_mp4(content):
            return
        raise ContentMismatchError(
            f"Content of '{filename}' does not match declared MIME type '{mime_type}'. "
            f"Expected MP4 ftyp box, got: {content[:12].hex()}..."
        )

    # Skip validation for MIME types we don't have signatures for
    if mime_type not in MAGIC_BYTES:
        logger.debug(
            "No magic byte signature defined for MIME type '%s', " "skipping validation for '%s'",
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
