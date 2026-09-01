"""Tests for built-in shortcodes (image, link, hero, code)."""

from __future__ import annotations

import logging
from collections.abc import Mapping

import pytest

from platzky.content_types import BUILTIN_CONTENT_TYPES, ContentType
from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.shortcodes.builtins import get_builtin_shortcodes


class _BuiltinTestPlugin(ContentTransformerPluginBase):
    accepted_content_types: Mapping[ContentType, str] = dict.fromkeys(
        BUILTIN_CONTENT_TYPES, "Exercised by tests."
    )


_BuiltinTestPlugin.shortcodes = get_builtin_shortcodes()


def _apply(content: str) -> str:
    return _BuiltinTestPlugin({}).transform_content(content)


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

    def test_protocol_relative_url_rejected(self) -> None:
        """No scheme, but external all the same."""
        assert _apply('[image url="//evil.example/x.png"]') == ""

    def test_root_relative_url_allowed(self) -> None:
        assert _apply('[image url="/x.jpg"]') == '<img src="/x.jpg" alt="">'


class TestLinkShortcode:
    def test_renders_anchor_tag(self) -> None:
        result = _apply('[link url="https://example.com"]Click here[/link]')
        assert result == '<a href="https://example.com">Click here</a>'

    def test_target_attr_included_when_given(self) -> None:
        result = _apply('[link url="https://example.com" target="_blank"]Go[/link]')
        assert 'target="_blank"' in result
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


class TestHeroShortcode:
    def test_wraps_content_in_hero_div(self) -> None:
        result = _apply("[hero]<h1>Headline</h1><p>Subheading text</p>[/hero]")
        assert result == '<div class="hero"><h1>Headline</h1><p>Subheading text</p></div>'

    def test_plain_text_content(self) -> None:
        result = _apply("[hero]Just some text[/hero]")
        assert result == '<div class="hero">Just some text</div>'


class TestCodeShortcode:
    def test_shortcodes_inside_are_shown_not_rendered(self) -> None:
        """The reason the tag exists: documenting a shortcode without invoking it."""
        result = _apply('[code][image url="/a.png"][/code]')
        assert result == '<pre><code>[image url="/a.png"]</code></pre>'

    def test_the_same_tag_outside_still_renders(self) -> None:
        assert _apply('[image url="/a.png"]') == '<img src="/a.png" alt="">'

    def test_html_inside_is_not_treated_specially(self) -> None:
        """``raw`` governs parsing only; what HTML does is STRIP_CONTENT_HTML's business."""
        result = _apply('[code]<img src="/a.png">[/code]')
        assert result == '<pre><code><img src="/a.png"></code></pre>'

    def test_whitespace_and_newlines_are_kept(self) -> None:
        result = _apply("[code]line1\n    line2[/code]")
        assert result == "<pre><code>line1\n    line2</code></pre>"

    def test_unclosed_code_tag_is_rejected(self) -> None:
        import pytest

        from platzky.shortcodes import ShortcodeError

        with pytest.raises(ShortcodeError, match=r"\[code\] is never closed"):
            _apply("[code]forever")
