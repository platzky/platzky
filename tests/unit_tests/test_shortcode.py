"""Tests for the shortcode parser."""

from platzky.content_types import ALL_CONTENT_TYPES, ContentType
from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.shortcodes import Shortcode, ShortcodeAttrs


def _apply_shortcodes(content: str, shortcodes: dict[str, Shortcode]) -> str:
    class _TestPlugin(ContentTransformerPluginBase):
        accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES

    _TestPlugin.shortcodes = shortcodes
    return _TestPlugin({}).transform_content(content)


def _sc(tag: str) -> Shortcode:
    """Build a minimal Shortcode for use in tests."""

    class _SC(Shortcode):
        name = tag
        description = "test"

        def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
            return f"[RENDERED:{tag}:{content}]"

    return _SC()


class TestApplyShortcodes:
    def test_empty_handlers_returns_content_unchanged(self) -> None:
        assert _apply_shortcodes("hello [foo]bar[/foo]", {}) == "hello [foo]bar[/foo]"

    def test_content_without_tags_returned_unchanged(self) -> None:
        sc = _sc("foo")
        assert _apply_shortcodes("<p>Hello world</p>", {"foo": sc}) == "<p>Hello world</p>"

    def test_unknown_tag_passes_through(self) -> None:
        sc = _sc("known")
        result = _apply_shortcodes("[unknown]text[/unknown]", {"known": sc})
        assert result == "[unknown]text[/unknown]"

    def test_block_tag_content_passed_to_handler(self) -> None:
        sc = _sc("greet")
        result = _apply_shortcodes("[greet]hello[/greet]", {"greet": sc})
        assert result == "[RENDERED:greet:hello]"

    def test_void_tag_calls_handler_with_empty_content(self) -> None:
        calls: list[tuple[ShortcodeAttrs, str]] = []

        class _ImgSC(Shortcode):
            name = "img"
            description = "test"

            def render(self, attrs: ShortcodeAttrs, content: str) -> str:
                calls.append((attrs, content))
                return "<img>"

        _apply_shortcodes('[img url="x.jpg"]', {"img": _ImgSC()})
        assert calls == [({"url": "x.jpg"}, "")]

    def test_attrs_parsed_into_dict(self) -> None:
        received: list[ShortcodeAttrs] = []

        class _FooSC(Shortcode):
            name = "foo"
            description = "test"

            def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
                received.append(attrs)
                return ""

        _apply_shortcodes('[foo color="#f00" size="large"]x[/foo]', {"foo": _FooSC()})
        assert received == [{"color": "#f00", "size": "large"}]

    def test_multiple_different_tags_both_replaced(self) -> None:
        a = _sc("a")
        b = _sc("b")
        result = _apply_shortcodes("[a]X[/a] and [b]Y[/b]", {"a": a, "b": b})
        assert "[RENDERED:a:X]" in result
        assert "[RENDERED:b:Y]" in result

    def test_unregistered_tag_between_registered_left_unchanged(self) -> None:
        sc = _sc("foo")
        result = _apply_shortcodes("[unknown]z[/unknown] [foo]x[/foo]", {"foo": sc})
        assert "[unknown]z[/unknown]" in result
        assert "[RENDERED:foo:x]" in result

    def test_multiline_content_preserved(self) -> None:
        sc = _sc("block")
        result = _apply_shortcodes("[block]line1\nline2[/block]", {"block": sc})
        assert result == "[RENDERED:block:line1\nline2]"
