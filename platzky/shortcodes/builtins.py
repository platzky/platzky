"""Built-in shortcode handlers for images and links."""

from __future__ import annotations

from urllib.parse import urlparse

from platzky.shortcode import Shortcode, ShortcodeAttr

_ALLOWED_SCHEMES = {"http", "https", ""}


def _image_handler(attrs: dict[str, str], _content: str) -> str:
    url = attrs.get("url", "")
    alt = attrs.get("alt", "")
    width = attrs.get("width", "")
    height = attrs.get("height", "")
    extra = ""
    if width:
        extra += f' width="{width}"'
    if height:
        extra += f' height="{height}"'
    return f'<img src="{url}" alt="{alt}"{extra}>'


def _link_handler(attrs: dict[str, str], content: str) -> str:
    url = attrs.get("url", "")
    target = attrs.get("target", "")
    if urlparse(url).scheme not in _ALLOWED_SCHEMES:
        return content
    target_attr = f' target="{target}"' if target else ""
    return f'<a href="{url}"{target_attr}>{content}</a>'


def get_builtin_shortcodes() -> dict[str, Shortcode]:
    """Return built-in shortcode descriptors for images and links."""
    return {
        "image": Shortcode(
            name="image",
            handler=_image_handler,
            description="Embed an image.",
            attributes=[
                ShortcodeAttr("url", "Image URL", required=True),
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
