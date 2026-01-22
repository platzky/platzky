"""Attachment size limits and related constants.

This module provides size limit constants and the AttachmentSizeError
exception for size validation failures.

Size Limits:
    The default maximum attachment size is 10MB (DEFAULT_MAX_ATTACHMENT_SIZE).
    This can be overridden per-attachment by passing a custom max_size parameter.
"""

# Default maximum attachment size: 10MB
DEFAULT_MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024


class AttachmentSizeError(ValueError):
    """Raised when attachment content exceeds the maximum allowed size.

    This is a subclass of ValueError for backwards compatibility with code
    that catches ValueError for size validation failures.
    """

    @classmethod
    def for_file(cls, filename: str, max_size: int, actual_size: int) -> "AttachmentSizeError":
        """Create an AttachmentSizeError with a formatted message."""
        message = (
            f"Attachment '{filename}' exceeds maximum size of "
            f"{max_size / (1024 * 1024):.2f}MB "
            f"(size: {actual_size / (1024 * 1024):.2f}MB)"
        )
        return cls(message)
