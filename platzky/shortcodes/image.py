"""Built-in image shortcode."""

from typing import ClassVar

from markupsafe import escape

from platzky.shortcodes import ShortcodeAttr
from platzky.shortcodes._url import is_url_allowed
from platzky.shortcodes.shortcode import Shortcode


class ImageShortcode(Shortcode):
    """Render an ``<img>`` tag from shortcode attributes."""

    name = "image"
    description = "Embed an image."
    attributes: ClassVar[list[ShortcodeAttr]] = [
        ShortcodeAttr("url", "Image URL (http/https or relative)", required=True),
        ShortcodeAttr("alt", "Alt text", required=False, default=""),
        ShortcodeAttr("width", "Width in pixels", required=False),
        ShortcodeAttr("height", "Height in pixels", required=False),
    ]
    example = '[image url="https://example.com/photo.jpg" alt="A photo"]'

    def handle(self, attrs: dict[str, str], content: str) -> str:  # noqa: ARG002
        """Render an img tag, returning empty string if the URL is not allowed."""
        url = attrs.get("url", "")
        if not is_url_allowed(url):
            return ""
        alt = escape(attrs.get("alt", ""))
        extra = ""
        if width := escape(attrs.get("width", "")):
            extra += f' width="{width}"'
        if height := escape(attrs.get("height", "")):
            extra += f' height="{height}"'
        return f'<img src="{escape(url)}" alt="{alt}"{extra}>'


image_shortcode = ImageShortcode()
