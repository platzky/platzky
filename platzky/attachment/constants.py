"""Attachment size limits and related constants."""

# Default maximum attachment size: 10MB
DEFAULT_MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024

# Legacy alias for backward compatibility
MAX_ATTACHMENT_SIZE = DEFAULT_MAX_ATTACHMENT_SIZE


class AttachmentSizeError(ValueError):
    """Raised when attachment content exceeds the maximum allowed size."""

    def __init__(self, filename: str, actual_size: int, max_size: int | None = None) -> None:
        self.filename = filename
        self.actual_size = actual_size
        self.max_size = max_size if max_size is not None else DEFAULT_MAX_ATTACHMENT_SIZE
        message = (
            f"Attachment '{filename}' exceeds maximum size of "
            f"{self.max_size / (1024 * 1024):.2f}MB "
            f"(size: {actual_size / (1024 * 1024):.2f}MB)"
        )
        super().__init__(message)
