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
