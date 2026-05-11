"""Example content-transformer plugin.

Two features:
- Wraps every letter 'a' in a red <span>.
- Adds a [red]...[/red] shortcode that wraps its content in a red <span>.
"""

import re
from typing import ClassVar

from markupsafe import Markup

from platzky.content_types import ContentType
from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.shortcodes import ShortcodeAttrs
from platzky.shortcodes.shortcode import Shortcode

_A_RE = re.compile(r"a")


class _RedShortcode(Shortcode):
    """Wrap content in a red <span>."""

    name = "red"
    description = "Render content in red."
    example = "[red]danger[/red]"

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Wrap content in a red span.

        Args:
            attrs: Unused.
            content: HTML content to colour red (may contain markup from earlier transforms).

        Returns:
            Content wrapped in ``<span style="color:red">``.
        """
        return str(Markup('<span style="color:red">{}</span>').format(Markup(content)))


class RedLetterPlugin(ContentTransformerPluginBase):
    """Colours every 'a' red and adds a [red] shortcode."""

    accepted_content_types: frozenset[ContentType] = frozenset({"post", "page"})
    shortcodes: ClassVar[dict[str, Shortcode]] = {"red": _RedShortcode()}

    def transform_text(self, text: str) -> str:
        """Wrap each 'a' in a red span.

        Args:
            text: Plain-text segment (no shortcode tag markup).

        Returns:
            Text with every 'a' wrapped in ``<span style="color:red">``.
        """
        return _A_RE.sub('<span style="color:red">a</span>', text)
