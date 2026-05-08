"""Tests for built-in shortcodes (image, link)."""

from __future__ import annotations

from platzky.shortcode import apply_shortcodes
from platzky.shortcodes.builtins import get_builtin_shortcodes


def _apply(content: str) -> str:
    return apply_shortcodes(content, get_builtin_shortcodes())


class TestImageShortcode:
    def test_renders_img_tag(self) -> None:
        result = _apply('[image url="https://example.com/photo.jpg" alt="A photo"]')
        assert '<img src="https://example.com/photo.jpg" alt="A photo">' == result

    def test_alt_defaults_to_empty(self) -> None:
        result = _apply('[image url="https://example.com/x.jpg"]')
        assert 'alt=""' in result

    def test_width_and_height_included(self) -> None:
        result = _apply('[image url="x.jpg" alt="" width="400" height="300"]')
        assert 'width="400"' in result
        assert 'height="300"' in result

    def test_missing_optional_attrs_omitted(self) -> None:
        result = _apply('[image url="x.jpg"]')
        assert "width" not in result
        assert "height" not in result


class TestLinkShortcode:
    def test_renders_anchor_tag(self) -> None:
        result = _apply('[link url="https://example.com"]Click here[/link]')
        assert result == '<a href="https://example.com">Click here</a>'

    def test_target_attr_included_when_given(self) -> None:
        result = _apply('[link url="https://example.com" target="_blank"]Go[/link]')
        assert 'target="_blank"' in result

    def test_javascript_url_returns_content_only(self) -> None:
        result = _apply('[link url="javascript:alert(1)"]click[/link]')
        assert "<a" not in result
        assert "click" in result

    def test_relative_url_allowed(self) -> None:
        result = _apply('[link url="/about"]About[/link]')
        assert '<a href="/about">About</a>' == result

    def test_data_url_rejected(self) -> None:
        result = _apply('[link url="data:text/html,<h1>x</h1>"]x[/link]')
        assert "<a" not in result
