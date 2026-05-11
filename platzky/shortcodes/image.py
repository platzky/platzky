"""Built-in image shortcode."""

from __future__ import annotations

from markupsafe import escape

from platzky.shortcodes import Shortcode, ShortcodeAttr
from platzky.shortcodes._url import is_url_allowed


def _image_handler(attrs: dict[str, str], _content: str) -> str:
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


image_shortcode = Shortcode(
    name="image",
    handler=_image_handler,
    description="Embed an image.",
    attributes=[
        ShortcodeAttr("url", "Image URL (http/https or relative)", required=True),
        ShortcodeAttr("alt", "Alt text", required=False, default=""),
        ShortcodeAttr("width", "Width in pixels", required=False),
        ShortcodeAttr("height", "Height in pixels", required=False),
    ],
    example='[image url="https://example.com/photo.jpg" alt="A photo"]',
)
