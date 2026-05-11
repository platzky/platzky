"""ContentFilterPluginBase capability — plugins that transform content."""

from __future__ import annotations

from abc import ABC

import jinja2.ext

from platzky.content_types import ContentType
from platzky.plugin.plugin import PluginBase
from platzky.shortcodes import Shortcode, apply_shortcodes


class ContentFilterPluginBase(PluginBase, ABC):
    """Base class for content-filter plugins.

    Subclasses declare which content types they want to transform via
    ``accepted_content_types``. The engine enforces final routing — plugins
    cannot bypass user-configured content-type restrictions.

    Override ``filter_content`` for arbitrary text transformations (e.g. emoji
    replacement). Override ``get_content_tags`` to register shortcode tags; the
    default ``filter_content`` applies them automatically.
    """

    accepted_content_types: set[ContentType]

    def filter_content(self, content: str) -> str:
        """Apply this plugin's transformation to a content string.

        Default: applies shortcodes returned by ``get_content_tags()``.
        Override for arbitrary transformations that don't use shortcode syntax.

        Args:
            content: Raw content string to transform.

        Returns:
            Transformed content string.
        """
        tags = self.get_content_tags()
        return apply_shortcodes(content, tags) if tags else content

    def get_content_tags(self) -> dict[str, Shortcode]:
        """Return ``{tag_name: Shortcode}`` for shortcode tags in content.

        Used by the default ``filter_content()`` and exposed on the admin help page.

        Returns:
            Map of tag name to Shortcode; empty dict if no shortcodes registered.
        """
        return {}

    def get_jinja_extensions(self) -> list[type[jinja2.ext.Extension]]:
        """Return Jinja2 extension classes to register with the template engine.

        Returns:
            Jinja2 extension classes to register; empty list by default.
        """
        return []
