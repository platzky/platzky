"""Shortcode package for blog post content."""

from platzky.shortcodes.shortcode import (
    Shortcode,
    ShortcodeAttr,
    ShortcodeAttrs,
    ShortcodeError,
    ShortcodeKind,
)
from platzky.shortcodes.urls import (
    EMBED_SCHEMES,
    LINK_SCHEMES,
    is_url_allowed,
    rejection_reason,
)

__all__ = [
    "EMBED_SCHEMES",
    "LINK_SCHEMES",
    "Shortcode",
    "ShortcodeAttr",
    "ShortcodeAttrs",
    "ShortcodeError",
    "ShortcodeKind",
    "is_url_allowed",
    "rejection_reason",
]
