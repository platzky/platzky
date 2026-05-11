"""Tests for the shortcode parser."""

from platzky.shortcodes import Shortcode, ShortcodeAttrs, make_shortcode_applier


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
        assert make_shortcode_applier({})("hello [foo]bar[/foo]") == "hello [foo]bar[/foo]"

    def test_content_without_tags_returned_unchanged(self) -> None:
        sc = _sc("foo")
        assert make_shortcode_applier({"foo": sc})("<p>Hello world</p>") == "<p>Hello world</p>"

    def test_unknown_tag_passes_through(self) -> None:
        sc = _sc("known")
        result = make_shortcode_applier({"known": sc})("[unknown]text[/unknown]")
        assert result == "[unknown]text[/unknown]"

    def test_block_tag_content_passed_to_handler(self) -> None:
        sc = _sc("greet")
        result = make_shortcode_applier({"greet": sc})("[greet]hello[/greet]")
        assert result == "[RENDERED:greet:hello]"

    def test_void_tag_calls_handler_with_empty_content(self) -> None:
        calls: list[tuple[ShortcodeAttrs, str]] = []

        class _ImgSC(Shortcode):
            name = "img"
            description = "test"

            def render(self, attrs: ShortcodeAttrs, content: str) -> str:
                calls.append((attrs, content))
                return "<img>"

        make_shortcode_applier({"img": _ImgSC()})('[img url="x.jpg"]')
        assert calls == [({"url": "x.jpg"}, "")]

    def test_attrs_parsed_into_dict(self) -> None:
        received: list[ShortcodeAttrs] = []

        class _FooSC(Shortcode):
            name = "foo"
            description = "test"

            def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
                received.append(attrs)
                return ""

        make_shortcode_applier({"foo": _FooSC()})('[foo color="#f00" size="large"]x[/foo]')
        assert received == [{"color": "#f00", "size": "large"}]

    def test_multiple_different_tags_both_replaced(self) -> None:
        a = _sc("a")
        b = _sc("b")
        result = make_shortcode_applier({"a": a, "b": b})("[a]X[/a] and [b]Y[/b]")
        assert "[RENDERED:a:X]" in result
        assert "[RENDERED:b:Y]" in result

    def test_unregistered_tag_between_registered_left_unchanged(self) -> None:
        sc = _sc("foo")
        result = make_shortcode_applier({"foo": sc})("[unknown]z[/unknown] [foo]x[/foo]")
        assert "[unknown]z[/unknown]" in result
        assert "[RENDERED:foo:x]" in result

    def test_multiline_content_preserved(self) -> None:
        sc = _sc("block")
        result = make_shortcode_applier({"block": sc})("[block]line1\nline2[/block]")
        assert result == "[RENDERED:block:line1\nline2]"
