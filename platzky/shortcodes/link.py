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
            ShortcodeAttr(
                "target",
                'Link target, e.g. "_blank" — automatically adds rel="noopener noreferrer"',
                required=False,
            ),
            ShortcodeAttr(
                "rel",
                "Relationship tokens, space separated: sponsored, nofollow, ugc, noopener, "
                "noreferrer. Other tokens are dropped; the link still renders.",
                required=False,
            ),
        ]
    )
    example = '[link url="https://example.com"]Click here[/link]'
    notes = (
        'target="_blank" always adds noopener and noreferrer to rel, even when rel is '
        'also set — your own tokens are kept, not overwritten. Use "sponsored" for '
        "affiliate and paid links."
    )

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

    #: The words a ``[link]`` tag's own ``rel`` attribute is allowed to contain. An
    #: allowlist, because ``rel`` is read by search engines and browsers, not just by a
    #: reader: ``sponsored``/``ugc`` are disclosures only the author writing the link can
    #: know to make (a paid link, someone else's content), and ``nofollow``/``noopener``/
    #: ``noreferrer`` change real crawler or browser behaviour — a stray or misspelled word
    #: here is not as harmless as a typo in prose.
    #:
    #: Unknown tokens are dropped, not refused: one mistyped word should cost its own token,
    #: not the whole link.
    #:
    #: Declared as a ClassVar beside ``url_policy`` for the same reason: an application with
    #: links platzky's do not describe can widen it by subclassing.
    permitted_rel: ClassVar[frozenset[str]] = frozenset(
        {"sponsored", "nofollow", "ugc", "noopener", "noreferrer"}
    )

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:
        """Render an anchor tag, refusing a URL the policy does not permit.

        A link with no destination is not a link, and its text is usually written to be
        clicked — "read more", "here" — so leaving that behind on its own reads as a
        mistake rather than as prose. The parser drops the whole element, text included.

        Content is embedded as-is per the ``render`` contract; only the attributes are
        escaped here.

        Args:
            attrs: Parsed shortcode attributes (url, target, rel).
            content: Link text.

        Returns:
            An ``<a>`` tag.

        Raises:
            UrlNotPermitted: If the URL is missing, or not one the policy permits.
        """
        self.url_policy.check(attrs.url)
        target_value = str(attrs.target or "")
        target_attr = f' target="{escape(target_value)}"' if target_value else ""
        tokens = {t for t in str(attrs.rel or "").lower().split() if t in self.permitted_rel}
        # Browsing context names are ASCII case-insensitive, so `_BLANK` opens a new
        # context too and needs the same rel. Unioned with whatever the author asked for
        # rather than replacing it: an author adding rel="sponsored" to a _blank link is
        # disclosing an affiliation, not volunteering to drop the opener protections.
        if target_value.lower() == "_blank":
            tokens |= {"noopener", "noreferrer"}
        rel_attr = f' rel="{" ".join(sorted(tokens))}"' if tokens else ""
        return f'<a href="{escape(attrs.url)}"{target_attr}{rel_attr}>{content}</a>'


link_shortcode = LinkShortcode()
