"""Tests for the shortcode parser."""

import pytest

from platzky.content_types import ALL_CONTENT_TYPES, ContentType
from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.shortcodes import Shortcode, ShortcodeAttr, ShortcodeAttrs


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


class TestShortcodeAttrs:
    def test_bool_true_when_schema_has_attrs(self) -> None:
        assert bool(ShortcodeAttrs([ShortcodeAttr("color", "desc")]))

    def test_bool_false_when_schema_is_empty(self) -> None:
        assert not bool(ShortcodeAttrs([]))

    def test_getattr_raises_for_unknown_name(self) -> None:
        attrs = ShortcodeAttrs([ShortcodeAttr("color", "desc")])
        with pytest.raises(AttributeError):
            _ = attrs.unknown

    def test_eq_with_shortcode_attrs_instance(self) -> None:
        a = ShortcodeAttrs([ShortcodeAttr("color", "desc")])
        b = ShortcodeAttrs([ShortcodeAttr("color", "desc")])
        a.values["color"] = "red"
        b.values["color"] = "red"
        assert a == b

    def test_eq_returns_not_implemented_for_other_types(self) -> None:
        attrs = ShortcodeAttrs([])
        assert attrs.__eq__(42) is NotImplemented

    def test_repr(self) -> None:
        attrs = ShortcodeAttrs([ShortcodeAttr("color", "desc")])
        assert "color" in repr(attrs)


class TestShortcodeSubclassing:
    def test_abstract_subclass_skips_name_validation(self) -> None:
        from abc import abstractmethod

        class _AbstractSC(Shortcode):
            @abstractmethod
            def render(self, attrs: ShortcodeAttrs, content: str) -> str: ...

        assert issubclass(_AbstractSC, Shortcode)

    def test_invalid_name_raises(self) -> None:
        def _render(_self: object, attrs: ShortcodeAttrs, content: str) -> str:
            return str(attrs) + content

        with pytest.raises(ValueError, match="valid `name`"):
            _ = type(
                "_BadSC",
                (Shortcode,),
                {"name": "123invalid", "description": "test", "render": _render},
            )

    def test_base_transform_field_value_non_dict_returns_scope_only(self) -> None:
        sc = _sc("mytag")
        assert sc.transform_field_value("anything") == {"scope": "mytag"}

    def test_base_transform_field_value_dict_merges_with_scope(self) -> None:
        sc = _sc("mytag")
        assert sc.transform_field_value({"color": "red"}) == {"scope": "mytag", "color": "red"}


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
