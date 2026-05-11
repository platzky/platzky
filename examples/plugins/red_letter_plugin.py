"""Example content-transformer plugin.

Two features:
- Wraps every letter 'a' in a red <span>.
- Adds a [red]...[/red] shortcode that wraps its content in a red <span>.
"""

import re

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
            content: Text to colour red.

        Returns:
            Content wrapped in ``<span style="color:red">``.
        """
        return f'<span style="color:red">{content}</span>'


class RedLetterPlugin(ContentTransformerPluginBase):
    """Colours every 'a' red and adds a [red] shortcode."""

    accepted_content_types: set[ContentType] = {"post", "page"}
    shortcodes = {"red": _RedShortcode()}

    def transform_content(self, content: str) -> str:
        """Apply shortcodes, then wrap each 'a' in a red span.

        Args:
            content: Raw post/page content.

        Returns:
            Transformed content with red 'a' letters and [red] shortcode resolved.
        """
        content = super().transform_content(content)
        return _A_RE.sub('<span style="color:red">a</span>', content)
