"""Built-in link shortcode."""

from typing import ClassVar

from markupsafe import escape

from platzky.shortcodes import ShortcodeAttr
from platzky.shortcodes._url import is_url_allowed
from platzky.shortcodes.shortcode import Shortcode


class LinkShortcode(Shortcode):
    """Render an ``<a>`` tag from shortcode attributes."""

    name = "link"
    description = "Create a hyperlink. Content becomes the link text."
    attributes: ClassVar[list[ShortcodeAttr]] = [
        ShortcodeAttr(
            "url",
            "Target URL (http/https or a relative path starting with /)",
            required=True,
        ),
        ShortcodeAttr("target", 'Link target, e.g. "_blank"', required=False),
    ]
    example = '[link url="https://example.com"]Click here[/link]'

    def handle(self, attrs: dict[str, str], content: str) -> str:
        """Render an anchor tag, returning raw content if the URL is not allowed."""
        url = attrs.get("url", "")
        if not is_url_allowed(url):
            return content
        target = escape(attrs.get("target", ""))
        target_attr = f' target="{target}"' if target else ""
        return f'<a href="{escape(url)}"{target_attr}>{escape(content)}</a>'


link_shortcode = LinkShortcode()
