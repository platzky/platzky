"""Built-in link shortcode."""

from typing import ClassVar

from markupsafe import escape

from platzky.shortcodes import ShortcodeAttr, ShortcodeAttrs
from platzky.shortcodes.shortcode import Shortcode
from platzky.shortcodes.urls import LINK_URL_POLICY, UrlPolicy


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

    #: The URL policy this shortcode enforces. Declared rather than looked up so an
    #: application can widen it by subclassing, for links that mean something platzky's do
    #: not::
    #:
    #:     class SmsLink(LinkShortcode):
    #:         name = "sms_link"
    #:         url_policy = UrlPolicy(LINK_URL_POLICY.schemes | {"sms"})
    #:
    #: Widening is the application's decision to make and its risk to own; the default is
    #: platzky's, and no site owner can change it from config, which is what keeps
    #: ``javascript:`` out of every deployment rather than out of the careful ones.
    url_policy: ClassVar[UrlPolicy] = LINK_URL_POLICY

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:
        """Render an anchor tag, refusing a URL the policy does not permit.

        A link with no destination is not a link, and its text is usually written to be
        clicked — "read more", "here" — so leaving that behind on its own reads as a
        mistake rather than as prose. The parser drops the whole element, text included.

        Content is embedded as-is per the ``render`` contract; only the attributes are
        escaped here.

        Args:
            attrs: Parsed shortcode attributes (url, target).
            content: Link text.

        Returns:
            An ``<a>`` tag.

        Raises:
            UrlNotPermitted: If the URL is missing, or not one the policy permits.
        """
        self.url_policy.check(attrs.url)
        target_value = str(attrs.target or "")
        target_attr = f' target="{escape(target_value)}"' if target_value else ""
        # Browsing context names are ASCII case-insensitive, so `_BLANK` opens a new
        # context too and needs the same rel.
        rel_attr = ' rel="noopener noreferrer"' if target_value.lower() == "_blank" else ""
        return f'<a href="{escape(attrs.url)}"{target_attr}{rel_attr}>{content}</a>'


link_shortcode = LinkShortcode()
