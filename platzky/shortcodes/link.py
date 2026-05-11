"""Built-in link shortcode."""

from markupsafe import escape

from platzky.shortcodes import ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes._url import is_url_allowed
from platzky.shortcodes.shortcode import Shortcode


class LinkShortcode(Shortcode):
    """Render an ``<a>`` tag from shortcode attributes."""

    name = "link"
    description = "Create a hyperlink. Content becomes the link text."
    attributes = ShortcodeAttrs(
        [
            ShortcodeAttr(
                "url",
                "Target URL (http/https or a relative path starting with /)",
                required=True,
            ),
            ShortcodeAttr("target", 'Link target, e.g. "_blank"', required=False),
        ]
    )
    example = '[link url="https://example.com"]Click here[/link]'

    def handle(self, attrs: ShortcodeAttrs, content: str) -> str:
        """Render an anchor tag, returning raw content if the URL is not allowed."""
        if not is_url_allowed(attrs.url):
            return content
        target_attr = f' target="{escape(attrs.target)}"' if attrs.target else ""
        return f'<a href="{escape(attrs.url)}"{target_attr}>{escape(content)}</a>'


link_shortcode = LinkShortcode()
