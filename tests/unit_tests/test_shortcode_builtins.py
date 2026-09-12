"""Tests for built-in shortcodes (image, link, hero, html, slideshow)."""

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
from platzky.shortcodes.slideshow import DEFAULT_WIDTH, MAX_SLIDES
from platzky.shortcodes.urls import LINK_URL_POLICY, UrlFault, UrlNotPermitted, UrlPolicy


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

    @pytest.mark.parametrize("attr", ["width", "height"])
    def test_a_size_that_is_not_whole_pixels_renders_nothing(
        self, attr: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``100%`` is not a valid HTML width; emitting it would only look like it worked."""
        with caplog.at_level(logging.WARNING):
            assert _apply(f'[image url="/x.jpg" {attr}="100%"]') == ""

        assert f"[image] rendered nothing: {attr} '100%'" in caplog.text

    def test_a_stored_size_is_checked_the_same_way(self) -> None:
        assert image_shortcode.render_value({"url": "/x.jpg", "width": "wide"}) == ""

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
        assert "its scheme is not permitted here" in caplog.text
        assert "use http or https" in caplog.text

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

    def test_rel_tokens_are_emitted(self) -> None:
        result = _apply('[link url="https://example.com" rel="sponsored"]Buy[/link]')
        assert 'rel="sponsored"' in result

    def test_rel_unions_with_the_rel_that_blank_forces(self) -> None:
        """Disclosing an affiliation is not volunteering to drop opener protection."""
        result = _apply(
            '[link url="https://example.com" rel="sponsored" target="_blank"]Buy[/link]'
        )
        assert 'rel="noopener noreferrer sponsored"' in result

    def test_unknown_rel_tokens_are_dropped_without_losing_the_link(self) -> None:
        """One mistyped word costs its own token, not the whole link."""
        result = _apply('[link url="https://example.com" rel="sponsred nofollow"]Buy[/link]')
        assert 'rel="nofollow"' in result
        assert "sponsred" not in result

    def test_rel_that_allowlists_nothing_emits_no_attribute(self) -> None:
        result = _apply('[link url="https://example.com" rel="evil"]x[/link]')
        assert "rel=" not in result

    def test_rel_is_case_insensitive(self) -> None:
        assert 'rel="sponsored"' in _apply('[link url="https://e.com" rel="SPONSORED"]x[/link]')

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
        ("url", "fault"),
        [
            ("https://example.com", None),
            ("/about", None),
            ("/", None),
            ("", UrlFault.NO_URL),
            ("photo.jpg", UrlFault.RELATIVE_PATH),
            ("//example.com/x", UrlFault.PROTOCOL_RELATIVE),
            ("javascript:alert(1)", UrlFault.SCHEME_NOT_PERMITTED),
            ("ftp://example.com/x", UrlFault.SCHEME_NOT_PERMITTED),
        ],
    )
    def test_every_url_is_sorted_into_the_fault_it_broke(
        self, url: str, fault: UrlFault | None
    ) -> None:
        """The whole classification in one table: what passes, and which rule catches the rest."""
        if fault is None:
            assert self._narrow.check(url) is None
            return
        with pytest.raises(UrlNotPermitted) as refusal:
            self._narrow.check(url)
        assert refusal.value.fault is fault

    def test_a_permitted_url_passes_quietly(self) -> None:
        """There is no verdict to unpack on the way through — which is the whole reason the
        check raises rather than reports: the approved path has nothing to say."""
        assert self._wide.check("mailto:hello@example.com") is None

    def test_each_policy_names_its_own_schemes(self) -> None:
        """What would have worked differs per policy, so the advice cannot be a constant."""
        with pytest.raises(UrlNotPermitted, match=r"use https$"):
            self._narrow.check("ftp://x")
        with pytest.raises(UrlNotPermitted, match=r"use https or mailto$"):
            self._wide.check("ftp://x")

    def test_no_fault_phrase_can_quote_a_url_back(self) -> None:
        """The phrases are fixed strings chosen up front, so a url cannot reach a log through
        one — which is the whole reason classifying and wording are separate jobs."""
        secret = "ftp://user:secret@example.com/signed?token=abc"
        with pytest.raises(UrlNotPermitted) as refusal:
            self._narrow.check(secret)
        assert "secret" not in str(refusal.value)
        assert "token" not in str(refusal.value)
        for fault in UrlFault:
            assert "secret" not in fault.value
            assert "token" not in fault.value

    @pytest.mark.parametrize(
        "url",
        ["/\\evil.example/x", "\\\\evil.example/x", "\\/evil.example/x", "//evil.example/x"],
    )
    def test_an_authority_is_refused_however_its_slashes_are_spelled(self, url: str) -> None:
        """A browser reads `\\` as `/` for special schemes, so these all reach a host."""
        with pytest.raises(UrlNotPermitted) as refusal:
            LINK_URL_POLICY.check(url)
        assert refusal.value.fault is UrlFault.PROTOCOL_RELATIVE

    def test_a_rooted_path_is_still_allowed(self) -> None:
        """The backslash guard must not catch an ordinary rooted path."""
        assert LINK_URL_POLICY.check("/about") is None
        assert LINK_URL_POLICY.check("/") is None

    def test_a_policy_permitting_no_scheme_still_takes_a_rooted_path(self) -> None:
        """Rooted-paths-only is a real policy. Its advice used to IndexError off an empty
        scheme list, failing a whole page render rather than refusing one url."""
        paths_only = UrlPolicy(frozenset())
        assert paths_only.check("/about") is None
        with pytest.raises(UrlNotPermitted, match=r"use a path starting with '/'$"):
            paths_only.check("https://example.com")

    def test_the_advice_is_never_a_scheme_the_policy_itself_refuses(self) -> None:
        """It used to hardcode http(s) — advice a policy like this one then also refuses."""
        with pytest.raises(UrlNotPermitted, match=r"use mailto$"):
            UrlPolicy(frozenset({"mailto"})).check("//host/path")

    def test_an_uppercase_scheme_is_refused_at_construction(self) -> None:
        """``urlparse`` lowercases what it parses, so an uppercase declaration matches
        nothing while advising the very scheme it had just refused. Refused where it is
        written rather than silently rewritten: this is a security declaration, and its
        author is entitled to have it mean what they wrote."""
        with pytest.raises(ValueError, match="lowercase"):
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
        assert policy.check("svn+ssh://host/repo") is None
        assert policy.check("myapp://open") is None

    def test_link_urls_accepts_contact_schemes(self) -> None:
        """The one thing specific to the real ``LINK_URL_POLICY``: it is public because goodmap
        needs to agree with it, and that only works if mailto/tel are actually in it."""
        assert LINK_URL_POLICY.check("mailto:hello@example.com") is None
        assert LINK_URL_POLICY.check("tel:+48123456789") is None


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


class TestSlideshowShortcode:
    def test_wraps_nested_images_and_counts_them(self) -> None:
        result = _apply('[slideshow][image url="/a.jpg"][image url="/b.jpg"][/slideshow]')
        assert result.startswith('<div class="slideshow" data-slides="2"')
        assert '<img src="/a.jpg" alt="">' in result
        assert '<img src="/b.jpg" alt="">' in result

    def test_default_interval_when_unspecified(self) -> None:
        result = _apply('[slideshow][image url="/a.jpg"][image url="/b.jpg"][/slideshow]')
        assert "--platzky-slideshow-interval: 4000ms" in result

    def test_interval_attribute_is_used(self) -> None:
        result = _apply('[slideshow interval="2500"][image url="/a.jpg"][/slideshow]')
        assert "--platzky-slideshow-interval: 2500ms" in result

    @pytest.mark.parametrize("written", ["100", "999999"])
    def test_out_of_range_interval_drops_the_whole_slideshow(
        self, written: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The floor is a seizure-risk threshold: outside the range costs the whole tag."""
        with caplog.at_level(logging.WARNING):
            result = _apply(f'[slideshow interval="{written}"][image url="/a.jpg"][/slideshow]')
        assert result == ""
        assert "[slideshow] rendered nothing" in caplog.text

    def test_unparseable_interval_drops_the_whole_slideshow(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A typo in one attribute must not take the whole page down — just its own tag."""
        with caplog.at_level(logging.WARNING):
            result = _apply('[slideshow interval="soon"][image url="/a.jpg"][/slideshow]')
        assert result == ""
        assert "[slideshow] rendered nothing" in caplog.text

    def test_more_slides_than_can_rotate_still_render(self) -> None:
        """A count the stylesheet has no rules for renders as a plain sequence.

        The failure to avoid is a missing CSS rule silently hiding an image someone wrote,
        so the count is reported honestly and the stacking rules simply do not match it.
        """
        images = "".join(f'[image url="/{n}.jpg"]' for n in range(MAX_SLIDES + 1))
        result = _apply(f"[slideshow]{images}[/slideshow]")
        assert f'data-slides="{MAX_SLIDES + 1}"' in result
        for n in range(MAX_SLIDES + 1):
            assert f'src="/{n}.jpg"' in result

    def test_a_refused_image_url_is_not_counted_as_a_slide(self) -> None:
        """The parser drops a refused element, so the count reflects what survived."""
        result = _apply(
            '[slideshow][image url="/a.jpg"][image url="javascript:alert(1)"][/slideshow]'
        )
        assert 'data-slides="1"' in result
        assert "javascript:" not in result

    def test_nested_shortcodes_are_rendered_before_the_wrapper_sees_them(self) -> None:
        """The wrapper is handed markup its children already produced, one entry each."""
        result = _apply('[slideshow][link url="https://e.com"]x[/link][/slideshow]')
        assert '<a href="https://e.com">x</a>' in result
        assert 'data-slides="1"' in result

    def test_text_between_the_frames_is_not_a_frame(self) -> None:
        """Only elements are counted, since only elements are what the stylesheet rotates."""
        result = _apply('[slideshow] [image url="/a.jpg"] and [image url="/b.jpg"] [/slideshow]')
        assert 'data-slides="2"' in result


class TestFigureShortcode:
    def test_wraps_its_image_and_caption_in_a_figure_div(self) -> None:
        result = _apply('[figure image="/a.jpg" alt="cover"]The first chapter.[/figure]')
        assert result == (
            '<div class="platzky-figure"><img src="/a.jpg" alt="cover">The first chapter.</div>'
        )

    def test_alt_defaults_to_empty(self) -> None:
        result = _apply('[figure image="/a.jpg"]The first chapter.[/figure]')
        assert result == (
            '<div class="platzky-figure"><img src="/a.jpg" alt="">The first chapter.</div>'
        )

    def test_missing_image_renders_nothing(self) -> None:
        """The image is required: without one, a figure is dropped like a bare [image] is."""
        result = _apply("[figure]No image here.[/figure]")
        assert result == ""

    def test_a_size_that_is_not_whole_pixels_renders_nothing(self) -> None:
        assert _apply('[figure image="/a.jpg" height="tall"]Caption.[/figure]') == ""

    def test_a_frame_counts_as_one_slide_not_as_its_contents(self) -> None:
        """A picture and its caption are one frame."""
        result = _apply(
            '[slideshow][figure image="/a.jpg"]One.[/figure]'
            '[figure image="/b.jpg"]Two.[/figure][/slideshow]'
        )
        assert 'data-slides="2"' in result

    def test_bare_images_still_count_as_frames_of_their_own(self) -> None:
        """The plain form keeps working: a slideshow of nothing but pictures needs no wrapper."""
        result = _apply('[slideshow][image url="/a.jpg"][image url="/b.jpg"][/slideshow]')
        assert 'data-slides="2"' in result
        assert 'class="platzky-figure"' not in result

    def test_a_caption_that_renders_its_own_div_adds_no_frame(self) -> None:
        """Counting markup ended the frame at the caption's ``</div>`` and overcounted."""
        result = _apply(
            '[slideshow][figure image="/a.jpg"]cap [hero]x[/hero][/figure]'
            '[figure image="/b.jpg"]Two.[/figure][/slideshow]'
        )
        assert 'data-slides="2"' in result

    def test_raw_html_in_a_caption_adds_no_frame(self) -> None:
        """An ``[html]`` body is verbatim, so no stripping pass can save a count from it."""
        result = _apply(
            '[slideshow][figure image="/a.jpg"]cap [html]<div>x</div>[/html]'
            ' [image url="/b.jpg"][/figure][/slideshow]'
        )
        assert 'data-slides="1"' in result

    def test_a_figure_and_a_bare_image_each_count_as_one_frame(self) -> None:
        """Mixing forms should not undercount: one frame plus one bare image is two."""
        result = _apply(
            '[slideshow][figure image="/a.jpg"]One.[/figure][image url="/b.jpg"][/slideshow]'
        )
        assert 'data-slides="2"' in result


class TestSlideshowWidth:
    def test_defaults_to_fitting_its_frames(self) -> None:
        result = _apply('[slideshow][image url="/a.jpg"][/slideshow]')
        assert f'data-width="{DEFAULT_WIDTH}"' in result

    def test_full_spans_its_container(self) -> None:
        result = _apply('[slideshow width="full"][image url="/a.jpg"][/slideshow]')
        assert 'data-width="full"' in result

    def test_width_is_matched_exactly(self) -> None:
        """Nothing is rewritten on the way, so ``FULL`` is refused rather than lowercased."""
        assert _apply('[slideshow width="FULL"][image url="/a.jpg"][/slideshow]') == ""

    def test_an_unknown_width_drops_the_whole_slideshow(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """One mistyped attribute should cost a log line and its own tag, not the page."""
        with caplog.at_level(logging.WARNING):
            result = _apply('[slideshow width="wide"][image url="/a.jpg"][/slideshow]')
        assert result == ""
        assert "[slideshow] rendered nothing" in caplog.text

    def test_an_invalid_width_with_injected_markup_still_renders_nothing(self) -> None:
        """Nothing written for an unrecognised width ever reaches the page, injected or not."""
        result = _apply('[slideshow width="full<script>"][image url="/a.jpg"][/slideshow]')
        assert result == ""
