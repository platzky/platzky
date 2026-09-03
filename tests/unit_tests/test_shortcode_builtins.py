"""Tests for built-in shortcodes (image, link, hero, html)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import ClassVar

import pytest
from markupsafe import Markup

from platzky.content_types import BUILTIN_CONTENT_TYPES, POST, ContentType
from platzky.plugin.content_transformer import (
    ContentTransformerPluginBase,
    ContentTransformerRegistry,
)
from platzky.shortcodes.builtins import get_builtin_shortcodes
from platzky.shortcodes.image import image_shortcode
from platzky.shortcodes.link import LinkShortcode, link_shortcode
from platzky.shortcodes.urls import LINK_URL_POLICY, UrlPolicy


class _BuiltinTestPlugin(ContentTransformerPluginBase):
    accepted_content_types: Mapping[ContentType, str] = dict.fromkeys(
        BUILTIN_CONTENT_TYPES, "Exercised by tests."
    )


_BuiltinTestPlugin.shortcodes = get_builtin_shortcodes()


def _apply(content: str) -> str:
    """Render content the way an application does: through a granted registry.

    ``Markup`` because a post body is content its caller vouched for, which is where the
    built-ins are used and what makes malformed tags an error rather than a passthrough.
    """
    plugin = _BuiltinTestPlugin({})
    registry = ContentTransformerRegistry(BUILTIN_CONTENT_TYPES)
    registry.grant(plugin, frozenset({POST}))
    return registry.transform_content([plugin], Markup(content), POST)


class TestImageShortcode:
    def test_renders_img_tag(self) -> None:
        result = _apply('[image url="https://example.com/photo.jpg" alt="A photo"]')
        assert '<img src="https://example.com/photo.jpg" alt="A photo">' == result

    def test_alt_defaults_to_empty(self) -> None:
        result = _apply('[image url="https://example.com/x.jpg"]')
        assert 'alt=""' in result

    def test_width_and_height_included(self) -> None:
        result = _apply('[image url="/x.jpg" alt="" width="400" height="300"]')
        assert 'width="400"' in result
        assert 'height="300"' in result

    def test_missing_optional_attrs_omitted(self) -> None:
        result = _apply('[image url="/x.jpg"]')
        assert result.startswith("<img")
        assert "width" not in result
        assert "height" not in result

    def test_missing_url_renders_nothing_and_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """An image with no source is not an image, and nobody can see an absence."""
        with caplog.at_level(logging.WARNING):
            assert _apply("[image]") == ""

        assert "[image] rendered nothing" in caplog.text

    def test_bare_relative_url_rejected(self) -> None:
        """``photo.jpg`` resolves against whichever page is showing the content."""
        assert _apply('[image url="photo.jpg"]') == ""

    def test_the_rejected_url_is_not_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """A rejected URL is where credentials and signed queries turn up; log the fault."""
        with caplog.at_level(logging.WARNING):
            assert _apply('[image url="ftp://user:s3cr3t@host/path?sig=abc"]') == ""

        assert "s3cr3t" not in caplog.text
        assert "sig=abc" not in caplog.text
        assert "host" not in caplog.text
        assert "scheme 'ftp' is not allowed" in caplog.text

    def test_protocol_relative_url_rejected(self) -> None:
        """No scheme, but external all the same."""
        assert _apply('[image url="//evil.example/x.png"]') == ""

    def test_the_url_description_matches_what_is_actually_accepted(self) -> None:
        """The description is shown on the help page; a bare relative url renders nothing."""
        description = next(a.description for a in image_shortcode.attributes if a.name == "url")
        assert "starting with /" in description
        assert _apply('[image url="photo.jpg"]') == ""

    def test_mailto_url_rejected(self) -> None:
        """An image is fetched, not navigated to, so the schemes a link accepts do not apply."""
        assert _apply('[image url="mailto:hello@example.com"]') == ""

    def test_tel_url_rejected(self) -> None:
        assert _apply('[image url="tel:+48123456789"]') == ""

    def test_root_relative_url_allowed(self) -> None:
        assert _apply('[image url="/x.jpg"]') == '<img src="/x.jpg" alt="">'


class TestLinkShortcode:
    def test_renders_anchor_tag(self) -> None:
        result = _apply('[link url="https://example.com"]Click here[/link]')
        assert result == '<a href="https://example.com">Click here</a>'

    def test_target_attr_included_when_given(self) -> None:
        result = _apply('[link url="https://example.com" target="_blank"]Go[/link]')
        assert 'target="_blank"' in result

    def test_uppercase_blank_still_gets_rel(self) -> None:
        """Browsing context names are case-insensitive, so _BLANK opens a new tab too."""
        result = _apply('[link url="https://example.com" target="_BLANK"]Go[/link]')
        assert 'rel="noopener noreferrer"' in result
        assert 'rel="noopener noreferrer"' in result

    def test_javascript_url_renders_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        """Link text is written to be clicked, so leaving it behind reads as a mistake."""
        with caplog.at_level(logging.WARNING):
            assert _apply('[link url="javascript:alert(1)"]click[/link]') == ""

        assert "[link] rendered nothing" in caplog.text

    def test_a_rejected_url_emits_nothing_at_all_for_a_stored_value(self) -> None:
        """The hostile path: nothing reaches the page, not even the escaped content."""
        link = get_builtin_shortcodes()["link"]
        result = link.render_value({"url": "javascript:alert(1)", "value": "<img src=x onerror=1>"})
        assert result == ""

    def test_missing_url_renders_nothing(self) -> None:
        assert _apply("[link]text[/link]") == ""

    def test_relative_url_allowed(self) -> None:
        result = _apply('[link url="/about"]About[/link]')
        assert '<a href="/about">About</a>' == result

    def test_data_url_rejected(self) -> None:
        result = _apply('[link url="data:text/html,<h1>x</h1>"]x[/link]')
        assert "<a" not in result

    def test_mailto_url_allowed(self) -> None:
        """An email address is an ordinary thing to publish, and a link is how it is read."""
        result = _apply('[link url="mailto:hello@example.com"]Email us[/link]')
        assert result == '<a href="mailto:hello@example.com">Email us</a>'

    def test_tel_url_allowed(self) -> None:
        result = _apply('[link url="tel:+48123456789"]Call us[/link]')
        assert result == '<a href="tel:+48123456789">Call us</a>'

    def test_rejection_names_the_schemes_a_link_accepts(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The reason has to say what would have worked, and a link accepts more than an image."""
        with caplog.at_level(logging.WARNING):
            _apply('[link url="ftp://example.com/x"]x[/link]')

        assert "use http, https, mailto or tel" in caplog.text


class TestLinkShortcodeUrlPolicyOverride:
    """An application may widen the link policy by subclassing; a site owner may not.

    Before this the policy was read from the module constant inside ``render``, so a subclass
    could declare its own and be silently overruled by the base — the class looked extensible
    and wasn't.
    """

    class _SmsLink(LinkShortcode):
        name = "sms_link"
        url_policy: ClassVar[UrlPolicy] = UrlPolicy(LINK_URL_POLICY.schemes | {"sms"})

    def test_a_subclass_can_widen_the_policy(self) -> None:
        rendered = self._SmsLink().render_value({"url": "sms:+48123456789", "content": "Text us"})
        assert rendered == '<a href="sms:+48123456789">Text us</a>'

    def test_widening_does_not_leak_into_the_builtin(self) -> None:
        """The subclass's grant is its own; ``[link]`` in a post is unaffected."""
        assert link_shortcode.render_value({"url": "sms:+48123456789", "content": "Text us"}) == ""

    @pytest.mark.parametrize(
        "url", ["javascript:alert(1)", "data:text/html,x", "/\\evil.example/x"]
    )
    def test_widening_opens_nothing_it_did_not_name(self, url: str) -> None:
        assert self._SmsLink().render_value({"url": url, "content": "X"}) == ""

    def test_the_log_names_the_subclass_tag(self, caplog: pytest.LogCaptureFixture) -> None:
        """A line saying "[link]" would send whoever reads it to the wrong shortcode."""
        with caplog.at_level(logging.WARNING):
            self._SmsLink().render_value({"url": "javascript:alert(1)", "content": "X"})

        assert "[sms_link] rendered nothing" in caplog.text


class TestUrlPolicy:
    """The policy object itself: one question, asked of a value that knows what it permits.

    Exercised through its own throwaway instances rather than the real policies, so a change
    to either's specific scheme set can never break a test of what ``UrlPolicy`` itself
    guarantees. The shortcode tests above already cover ``LINK_URL_POLICY`` and image's embed
    policy end to end.
    """

    _narrow = UrlPolicy(frozenset({"https"}))
    _wide = UrlPolicy(frozenset({"https", "mailto"}))

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com",
            "mailto:hello@example.com",
            "/about",
            "",
            "photo.jpg",
            "//example.com/x",
            "javascript:alert(1)",
            "ftp://example.com/x",
        ],
    )
    def test_allows_never_disagrees_with_rejection_reason(self, url: str) -> None:
        """The pair used to be two calls a caller had to keep in step; now one defines the other."""
        for policy in (self._narrow, self._wide):
            assert policy.allows(url) is (policy.rejection_reason(url) is None)

    def test_a_permitted_url_gives_no_reason(self) -> None:
        assert self._narrow.rejection_reason("https://example.com") is None

    def test_each_policy_names_its_own_schemes_when_refusing(self) -> None:
        """The message has to say what would have worked *for this policy*, and they differ."""
        assert str(self._narrow.rejection_reason("ftp://example.com")).endswith("use https")
        assert "https or mailto" in str(self._wide.rejection_reason("ftp://example.com"))

    def test_the_rejected_url_is_never_quoted_back(self) -> None:
        reason = self._narrow.rejection_reason("ftp://user:secret@example.com/signed?token=abc")
        assert reason is not None
        assert "secret" not in reason
        assert "token" not in reason

    @pytest.mark.parametrize(
        "url",
        ["/\\evil.example/x", "\\\\evil.example/x", "\\/evil.example/x", "//evil.example/x"],
    )
    def test_an_authority_is_refused_however_its_slashes_are_spelled(self, url: str) -> None:
        """A browser reads `\\` as `/` for special schemes, so these all reach a host."""
        assert not LINK_URL_POLICY.allows(url)
        assert "protocol-relative" in str(LINK_URL_POLICY.rejection_reason(url))

    def test_a_rooted_path_is_still_allowed(self) -> None:
        """The backslash guard must not catch an ordinary rooted path."""
        assert LINK_URL_POLICY.allows("/about")
        assert LINK_URL_POLICY.allows("/")

    def test_a_policy_permitting_no_scheme_does_not_raise(self) -> None:
        """Rooted-paths-only is a real policy. It used to IndexError out of ``allows``, which
        would fail a whole page render rather than refuse one url."""
        paths_only = UrlPolicy(frozenset())
        assert paths_only.allows("/about")
        assert not paths_only.allows("https://example.com")
        assert "path starting with '/'" in str(paths_only.rejection_reason("https://example.com"))

    def test_the_protocol_relative_reason_names_this_policy_s_schemes(self) -> None:
        """It used to hardcode http(s) — advice a policy like this one then also refuses."""
        assert "use mailto instead" in str(
            UrlPolicy(frozenset({"mailto"})).rejection_reason("//host/path")
        )

    def test_an_uppercase_scheme_is_refused_at_construction(self) -> None:
        """``urlparse`` lowercases what it parses, so an uppercase declaration matches
        nothing while advising the very scheme it had just refused. Refused where it is
        written rather than silently rewritten: this is a security declaration, and its
        author is entitled to have it mean what they wrote."""
        with pytest.raises(ValueError, match="must be lowercase"):
            UrlPolicy(frozenset({"HTTPS"}))

    @pytest.mark.parametrize(
        "scheme",
        [
            "https:",  # the colon belongs to the url, not to the scheme
            "ht tp",
            "2fast",  # a scheme starts with a letter
            "",
            "http/s",
        ],
    )
    def test_a_scheme_that_is_not_a_scheme_is_refused_at_construction(self, scheme: str) -> None:
        """Same silent failure as the uppercase case, from the same missing check."""
        with pytest.raises(ValueError, match="not a url scheme"):
            UrlPolicy(frozenset({scheme}))

    def test_the_unusual_but_legal_spellings_are_accepted(self) -> None:
        """RFC 3986 allows digits, '+', '-' and '.' after the first letter, and the registry
        is not consulted: a private scheme is the application's business, not platzky's."""
        policy = UrlPolicy(frozenset({"svn+ssh", "view-source", "z39.50r", "myapp"}))
        assert policy.allows("svn+ssh://host/repo")
        assert policy.allows("myapp://open")

    def test_link_urls_accepts_contact_schemes(self) -> None:
        """The one thing specific to the real ``LINK_URL_POLICY``: it is public because goodmap
        needs to agree with it, and that only works if mailto/tel are actually in it."""
        assert LINK_URL_POLICY.allows("mailto:hello@example.com")
        assert LINK_URL_POLICY.allows("tel:+48123456789")


class TestHeroShortcode:
    def test_wraps_content_in_hero_div(self) -> None:
        result = _apply("[hero]<h1>Headline</h1><p>Subheading text</p>[/hero]")
        assert result == '<div class="hero"><h1>Headline</h1><p>Subheading text</p></div>'

    def test_plain_text_content(self) -> None:
        result = _apply("[hero]Just some text[/hero]")
        assert result == '<div class="hero">Just some text</div>'


class TestHtmlShortcode:
    def test_shortcodes_inside_are_shown_not_rendered(self) -> None:
        """One reason the tag exists: documenting a shortcode without invoking it."""
        result = _apply('[html][image url="/a.png"][/html]')
        assert result == '[image url="/a.png"]'

    def test_the_same_tag_outside_still_renders(self) -> None:
        assert _apply('[image url="/a.png"]') == '<img src="/a.png" alt="">'

    def test_html_inside_reaches_the_page_as_html(self) -> None:
        """The other reason: marking HTML that is meant, where the rest is stripped."""
        result = _apply('[html]<img src="/a.png">[/html]')
        assert result == '<img src="/a.png">'

    def test_the_body_is_emitted_without_a_wrapper(self) -> None:
        result = _apply("[html]line1\n    line2[/html]")
        assert result == "line1\n    line2"

    def test_unclosed_html_tag_is_rejected(self) -> None:
        import pytest

        from platzky.shortcodes import ShortcodeError

        with pytest.raises(ShortcodeError, match=r"\[html\] is never closed"):
            _apply("[html]forever")
