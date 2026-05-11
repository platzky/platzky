"""Built-in image shortcode."""

from markupsafe import escape

from platzky.shortcodes import ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes._url import is_url_allowed
from platzky.shortcodes.shortcode import Shortcode


class ImageShortcode(Shortcode):
    """Render an ``<img>`` tag from shortcode attributes."""

    name = "image"
    description = "Embed an image."
    attributes = ShortcodeAttrs(
        [
            ShortcodeAttr("url", "Image URL (http/https or relative)", required=True),
            ShortcodeAttr("alt", "Alt text", required=False),
            ShortcodeAttr("width", "Width in pixels", required=False),
            ShortcodeAttr("height", "Height in pixels", required=False),
        ]
    )
    example = '[image url="https://example.com/photo.jpg" alt="A photo"]'

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Render an img tag, returning empty string if the URL is not allowed.

        Args:
            attrs: Parsed shortcode attributes (url, alt, width, height).
            content: Unused — image is a void element.

        Returns:
            An ``<img>`` tag, or empty string if the URL is not allowed.
        """
        if not is_url_allowed(attrs.url):
            return ""
        extra = ""
        if width := escape(attrs.width):
            extra += f' width="{width}"'
        if height := escape(attrs.height):
            extra += f' height="{height}"'
        return f'<img src="{escape(attrs.url)}" alt="{escape(attrs.alt)}"{extra}>'


image_shortcode = ImageShortcode()
