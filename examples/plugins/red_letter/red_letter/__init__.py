"""Example content-transformer plugin.

Two features:
- Wraps every letter 'a' in a red <span>.
- Adds a [red]...[/red] shortcode that wraps its content in a red <span>.
"""

import re
from collections.abc import Mapping
from typing import ClassVar

from markupsafe import Markup

from platzky.content_types import PAGE, POST, ContentType
from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.shortcodes import ShortcodeAttrs
from platzky.shortcodes.shortcode import Shortcode

_A_RE = re.compile(r"a")


class _RedShortcode(Shortcode):
    """Wrap content in a red <span>."""

    name = "red"
    description = "Render content in red."
    example = "[red]danger[/red]"

    def render(self, attrs: ShortcodeAttrs, content: Markup) -> str:  # noqa: ARG002
        """Wrap content in a red span.

        Embedded, not escaped. The pipeline runs every filter before it renders any tag,
        so a shortcode's content can already hold markup platzky produced. This plugin
        shows that on itself: ``transform_text`` colours every letter ``a``, and it reaches
        the text inside the tag first — so the ``danger`` in ``[red]danger[/red]`` arrives
        here as ``d<span style="color:red">a</span>nger``, not as plain text. Escaping it
        would put those spans on the page as visible characters instead of a red letter.

        Args:
            attrs: Unused.
            content: Inner content. ``Markup`` because the escaping decision was already
                taken upstream — escaped if nobody vouched for it, left as written if the
                caller did.

        Returns:
            Content wrapped in ``<span style="color:red">``.
        """
        return f'<span style="color:red">{content}</span>'


class RedLetterPlugin(ContentTransformerPluginBase):
    """Colours every 'a' red and adds a [red] shortcode."""

    accepted_content_types: Mapping[ContentType, str] = {
        POST: "Colours letters and renders [red] in post bodies.",
        PAGE: "Colours letters and renders [red] in page bodies.",
    }
    shortcodes: ClassVar[dict[str, Shortcode]] = {"red": _RedShortcode()}

    def transform_text(self, text: str) -> str:
        """Wrap each 'a' in a red span.

        Args:
            text: Plain-text segment (no shortcode tag markup).

        Returns:
            Text with every 'a' wrapped in ``<span style="color:red">``.
        """
        return _A_RE.sub('<span style="color:red">a</span>', text)
