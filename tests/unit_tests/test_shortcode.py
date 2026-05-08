"""Tests for the shortcode parser."""

from __future__ import annotations

from platzky.shortcodes import Shortcode, apply_shortcodes


def _sc(name: str) -> Shortcode:
    """Build a minimal Shortcode that records calls."""
    calls: list[tuple[dict[str, str], str]] = []

    def handler(attrs: dict[str, str], content: str) -> str:
        calls.append((attrs, content))
        return f"[RENDERED:{name}:{content}]"

    sc = Shortcode(name=name, handler=handler, description="test")
    sc._calls = calls  # type: ignore[attr-defined]
    return sc


class TestApplyShortcodes:
    def test_empty_handlers_returns_content_unchanged(self) -> None:
        assert apply_shortcodes("hello [foo]bar[/foo]", {}) == "hello [foo]bar[/foo]"

    def test_content_without_tags_returned_unchanged(self) -> None:
        sc = _sc("foo")
        assert apply_shortcodes("<p>Hello world</p>", {"foo": sc}) == "<p>Hello world</p>"

    def test_unknown_tag_passes_through(self) -> None:
        sc = _sc("known")
        result = apply_shortcodes("[unknown]text[/unknown]", {"known": sc})
        assert result == "[unknown]text[/unknown]"

    def test_block_tag_content_passed_to_handler(self) -> None:
        sc = _sc("greet")
        result = apply_shortcodes("[greet]hello[/greet]", {"greet": sc})
        assert result == "[RENDERED:greet:hello]"

    def test_void_tag_calls_handler_with_empty_content(self) -> None:
        calls: list[tuple[dict[str, str], str]] = []

        def handler(attrs: dict[str, str], content: str) -> str:
            calls.append((attrs, content))
            return "<img>"

        sc = Shortcode(name="img", handler=handler, description="test")
        apply_shortcodes('[img url="x.jpg"]', {"img": sc})
        assert calls == [({"url": "x.jpg"}, "")]

    def test_attrs_parsed_into_dict(self) -> None:
        received: list[dict[str, str]] = []

        def handler(attrs: dict[str, str], _content: str) -> str:
            received.append(attrs)
            return ""

        sc = Shortcode(name="foo", handler=handler, description="test")
        apply_shortcodes('[foo color="#f00" size="large"]x[/foo]', {"foo": sc})
        assert received == [{"color": "#f00", "size": "large"}]

    def test_multiple_different_tags_both_replaced(self) -> None:
        a = _sc("a")
        b = _sc("b")
        result = apply_shortcodes("[a]X[/a] and [b]Y[/b]", {"a": a, "b": b})
        assert "[RENDERED:a:X]" in result
        assert "[RENDERED:b:Y]" in result

    def test_unregistered_tag_between_registered_left_unchanged(self) -> None:
        sc = _sc("foo")
        result = apply_shortcodes("[unknown]z[/unknown] [foo]x[/foo]", {"foo": sc})
        assert "[unknown]z[/unknown]" in result
        assert "[RENDERED:foo:x]" in result

    def test_multiline_content_preserved(self) -> None:
        sc = _sc("block")
        result = apply_shortcodes("[block]line1\nline2[/block]", {"block": sc})
        assert result == "[RENDERED:block:line1\nline2]"
