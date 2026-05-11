"""ContentTransformerPluginBase capability — plugins that transform content."""

from __future__ import annotations

from abc import ABC

import jinja2.ext

from platzky.content_types import ContentType
from platzky.plugin.plugin import PluginBase
from platzky.shortcodes import Shortcode, make_shortcode_applier


class ContentTransformerPluginBase(PluginBase, ABC):
    """Base class for content-transformer plugins.

    Subclasses declare which content types they want to transform via
    ``accepted_content_types``. The engine enforces final routing — plugins
    cannot bypass user-configured content-type restrictions.

    Override ``transform_content`` for arbitrary text transformations (e.g. emoji
    replacement). Override ``get_supported_shortcodes`` to register shortcode tags; the
    default ``transform_content`` applies them automatically.
    """

    accepted_content_types: set[ContentType]

    def transform_content(self, content: str) -> str:
        """Apply this plugin's transformation to a content string.

        Default: applies shortcodes returned by ``get_supported_shortcodes()``.
        Override for arbitrary transformations that don't use shortcode syntax.

        Args:
            content: Raw content string to transform.

        Returns:
            Transformed content string.
        """
        return make_shortcode_applier(self.get_supported_shortcodes())(content)

    def get_supported_shortcodes(self) -> dict[str, Shortcode]:
        """Return shortcode tags this plugin handles.

        Used by the default ``transform_content()`` and exposed on the admin help page.

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
