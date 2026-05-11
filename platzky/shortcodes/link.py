"""Built-in link shortcode."""

from markupsafe import escape

from platzky.shortcodes import Shortcode, ShortcodeAttr
from platzky.shortcodes._url import is_url_allowed


def _link_handler(attrs: dict[str, str], content: str) -> str:
    url = attrs.get("url", "")
    if not is_url_allowed(url):
        return content
    target = escape(attrs.get("target", ""))
    target_attr = f' target="{target}"' if target else ""
    return f'<a href="{escape(url)}"{target_attr}>{escape(content)}</a>'


link_shortcode = Shortcode(
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
    example='[link url="https://example.com"]Click here[/link]',
)
