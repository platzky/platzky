"""Attachment size limits and related constants.

This module provides size limit constants for various services and the
AttachmentSizeError exception for size validation failures.

Size Limits:
    The default maximum attachment size is 10MB (DEFAULT_MAX_ATTACHMENT_SIZE).
    This default was chosen because 10MB is a common email attachment limit
    used by major email providers (Gmail, Outlook, etc.).

    For different services, use the provided presets:
    - EMAIL_MAX_SIZE (10MB): Standard email attachment limit
    - SLACK_MAX_SIZE (5MB): Slack file upload limit for free plans
    - DISCORD_MAX_SIZE (8MB): Discord file upload limit for non-Nitro users
    - TELEGRAM_MAX_SIZE (50MB): Telegram file upload limit
"""

# Default maximum attachment size: 10MB (common email attachment limit)
DEFAULT_MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024

# Service-specific size presets
EMAIL_MAX_SIZE = 10 * 1024 * 1024  # 10MB - Gmail, Outlook, most email providers
SLACK_MAX_SIZE = 5 * 1024 * 1024  # 5MB - Slack free plan limit
DISCORD_MAX_SIZE = 8 * 1024 * 1024  # 8MB - Discord non-Nitro limit
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024  # 50MB - Telegram file limit


class AttachmentSizeError(ValueError):
    """Raised when attachment content exceeds the maximum allowed size.

    This is a subclass of ValueError for backwards compatibility with code
    that catches ValueError for size validation failures.
    """
