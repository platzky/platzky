"""ContentTransformerPluginBase capability — plugins that transform content."""

from __future__ import annotations

import logging
import re
from abc import ABC
from itertools import zip_longest
from typing import ClassVar, final

import jinja2.ext

from platzky.content_types import ContentType
from platzky.plugin.plugin import PluginBase
from platzky.shortcodes import Shortcode, ShortcodeAttrs

logger = logging.getLogger(__name__)

_SHORTCODE_TAG_RE = re.compile(r"\[[^\]]*\]|<[^>]*>")

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

    Declare ``shortcodes`` to register shortcode tags; they are applied
    automatically by ``transform_content``. Override ``transform_text`` to
    apply plain-text transformations — the framework guarantees that
    ``transform_text`` is never called with shortcode tag markup so
    transformations cannot accidentally mangle tags intended for other plugins.
    """

    accepted_content_types: frozenset[ContentType] = frozenset()
    shortcodes: ClassVar[dict[str, Shortcode]] = {}

    def _warn_if_no_capabilities(self, plugin_name: str) -> None:
        """Log if accepted_content_types is empty, then delegate to super()."""
        super()._warn_if_no_capabilities(plugin_name)
        if not self.accepted_content_types:
            logger.debug(
                "Plugin %s declares no accepted_content_types; it will transform no content.",
                plugin_name,
            )

    @final
    def transform_content(self, content: str) -> str:
        """Split content on shortcode tags, transform plain-text segments, then apply shortcodes.

        Not overridable — override ``transform_text`` instead.

        Args:
            content: Raw content string to transform.

        Returns:
            Transformed content string.
        """
        parts = _SHORTCODE_TAG_RE.split(content)
        tags = _SHORTCODE_TAG_RE.findall(content)
        transformed = [self.transform_text(p) for p in parts]
        reassembled = "".join(
            segment for pair in zip_longest(transformed, tags, fillvalue="") for segment in pair
        )
        return _apply_shortcodes(reassembled, self.shortcodes)

    def transform_text(self, text: str) -> str:
        """Apply plain-text transformation to a non-tag content segment.

        Override this to transform plain text while the framework ensures
        shortcode tags are never passed here.

        Args:
            text: Plain-text segment (no shortcode tag markup).

        Returns:
            Transformed text.
        """
        return text

    def get_jinja_extensions(self) -> list[type[jinja2.ext.Extension]]:
        """Return Jinja2 extension classes to register with the template engine.

        Returns:
            Jinja2 extension classes to register; empty list by default.
        """
        return []
