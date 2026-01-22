"""Attachment size limits and related constants."""

# Maximum attachment size: 10MB
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024


class AttachmentSizeError(ValueError):
    """Raised when attachment content exceeds the maximum allowed size."""

    @classmethod
    def for_file(cls, filename: str, actual_size: int) -> "AttachmentSizeError":
        """Create an AttachmentSizeError with a formatted message."""
        message = (
            f"Attachment '{filename}' exceeds maximum size of "
            f"{MAX_ATTACHMENT_SIZE / (1024 * 1024):.2f}MB "
            f"(size: {actual_size / (1024 * 1024):.2f}MB)"
        )
        return cls(message)
