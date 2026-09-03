"""Built-in link shortcode."""

import logging

from markupsafe import escape

from platzky.shortcodes import ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.shortcode import Shortcode
from platzky.shortcodes.urls import LINK_URL_POLICY

logger = logging.getLogger(__name__)


class LinkShortcode(Shortcode):
    """Render an ``<a>`` tag from shortcode attributes."""

    name = "link"
    description = "Create a hyperlink. Content becomes the link text."
    attributes = ShortcodeAttrs(
        [
            ShortcodeAttr(
                "url",
                "Target URL (http/https/mailto/tel or a relative path starting with /)",
                required=True,
            ),
            ShortcodeAttr("target", 'Link target, e.g. "_blank"', required=False),
        ]
    )
    example = '[link url="https://example.com"]Click here[/link]'

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:
        """Render an anchor tag, or nothing at all when there is nowhere to link to.

        A link with no destination is not a link, and its text is usually written to be
        clicked — "read more", "here" — so leaving that behind on its own reads as a
        mistake rather than as prose. The whole tag renders to nothing, text included, and
        logs why, because an author cannot see an absence.

        Content is embedded as-is per the ``render`` contract; only the attributes are
        escaped here.

        Args:
            attrs: Parsed shortcode attributes (url, target).
            content: Link text.

        Returns:
            An ``<a>`` tag, or empty string if the URL is missing or not allowed.
        """
        if not LINK_URL_POLICY.allows(attrs.url):
            logger.warning(
                "[link] rendered nothing: %s.", LINK_URL_POLICY.rejection_reason(attrs.url)
            )
            return ""
        target_value = str(attrs.target or "")
        target_attr = f' target="{escape(target_value)}"' if target_value else ""
        # Browsing context names are ASCII case-insensitive, so `_BLANK` opens a new
        # context too and needs the same rel.
        rel_attr = ' rel="noopener noreferrer"' if target_value.lower() == "_blank" else ""
        return f'<a href="{escape(attrs.url)}"{target_attr}{rel_attr}>{content}</a>'


link_shortcode = LinkShortcode()
