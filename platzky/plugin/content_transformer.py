"""ContentTransformerPluginBase capability — plugins that transform content."""

from __future__ import annotations

import re
from abc import ABC
from typing import ClassVar

import jinja2.ext

from platzky.content_types import ContentType
from platzky.plugin.plugin import PluginBase
from platzky.shortcodes import Shortcode, ShortcodeAttrs

_MAX_ATTR_NAME_LEN = 100
_MAX_ATTR_VALUE_LEN = 2048
_ATTR_RE = re.compile(rf'([\w-]{{1,{_MAX_ATTR_NAME_LEN}}})="([^"]{{0,{_MAX_ATTR_VALUE_LEN}}})"')


def _apply_shortcodes(content: str, shortcodes: dict[str, Shortcode]) -> str:
    if not shortcodes:
        return content

    tag_names = "|".join(re.escape(n) for n in shortcodes)
    pattern = re.compile(
        rf"\[({tag_names})((?:\s+[\w-]+=\"[^\"]*\")*)\s*\](?:(.*?)\[/\1\])?",
        re.DOTALL,
    )

    def _apply(text: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            sc = shortcodes[m.group(1)]
            attrs = ShortcodeAttrs(list(sc.attributes))
            attrs.values = dict(_ATTR_RE.findall(m.group(2) or ""))
            inner = m.group(3) or ""
            if inner:
                inner = _apply(inner)
            return sc.render(attrs, inner)

        return pattern.sub(_replace, text)

    return _apply(content)


class ContentTransformerPluginBase(PluginBase, ABC):
    """Base class for content-transformer plugins.

    Subclasses declare which content types they want to transform via
    ``accepted_content_types``. The engine enforces final routing — plugins
    cannot bypass user-configured content-type restrictions.

    Declare ``shortcodes`` to register shortcode tags; the default
    ``transform_content`` applies them automatically. Override
    ``transform_content`` for arbitrary transformations that don't use
    shortcode syntax (e.g. emoji replacement).
    """

    accepted_content_types: frozenset[ContentType]
    shortcodes: ClassVar[dict[str, Shortcode]] = {}

    def transform_content(self, content: str) -> str:
        """Apply this plugin's transformation to a content string.

        Default: applies ``shortcodes``. Override for custom transformations.

        Args:
            content: Raw content string to transform.

        Returns:
            Transformed content string.
        """
        return _apply_shortcodes(content, self.shortcodes)

    def get_jinja_extensions(self) -> list[type[jinja2.ext.Extension]]:
        """Return Jinja2 extension classes to register with the template engine.

        Returns:
            Jinja2 extension classes to register; empty list by default.
        """
        return []
