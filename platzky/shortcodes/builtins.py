"""Built-in shortcode handlers for images and links."""

from __future__ import annotations

from urllib.parse import urlparse

from markupsafe import escape

from platzky.shortcodes import Shortcode, ShortcodeAttr

_ALLOWED_SCHEMES = {"http", "https", ""}


def _image_handler(attrs: dict[str, str], _content: str) -> str:
    """Render an ``<img>`` tag from shortcode attributes."""
    url = attrs.get("url", "")
    if urlparse(url).scheme not in _ALLOWED_SCHEMES:
        return ""
    alt = escape(attrs.get("alt", ""))
    extra = ""
    if width := escape(attrs.get("width", "")):
        extra += f' width="{width}"'
    if height := escape(attrs.get("height", "")):
        extra += f' height="{height}"'
    return f'<img src="{escape(url)}" alt="{alt}"{extra}>'


def _link_handler(attrs: dict[str, str], content: str) -> str:
    """Render an ``<a>`` tag from shortcode attributes, validating the URL scheme."""
    url = attrs.get("url", "")
    if urlparse(url).scheme not in _ALLOWED_SCHEMES:
        return content
    target = escape(attrs.get("target", ""))
    target_attr = f' target="{target}"' if target else ""
    return f'<a href="{escape(url)}"{target_attr}>{escape(content)}</a>'


def get_builtin_shortcodes() -> dict[str, Shortcode]:
    """Return built-in shortcode descriptors for images and links."""
    return {
        "image": Shortcode(
            name="image",
            handler=_image_handler,
            description="Embed an image.",
            attributes=[
                ShortcodeAttr("url", "Image URL (http/https or relative)", required=True),
                ShortcodeAttr("alt", "Alt text", required=False, default=""),
                ShortcodeAttr("width", "Width in pixels", required=False),
                ShortcodeAttr("height", "Height in pixels", required=False),
            ],
            has_content=False,
            example='[image url="https://example.com/photo.jpg" alt="A photo"]',
        ),
        "link": Shortcode(
            name="link",
            handler=_link_handler,
            description="Create a hyperlink. Content becomes the link text.",
            attributes=[
                ShortcodeAttr(
                    "url",
                    "Target URL (http/https or a relative path starting with /)",
                    required=True,
                ),
                ShortcodeAttr("target", 'Link target, e.g. "_blank"', required=False),
            ],
            has_content=True,
            example='[link url="https://example.com"]Click here[/link]',
        ),
    }
