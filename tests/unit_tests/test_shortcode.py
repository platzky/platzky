"""Tests for the shortcode parser."""

import logging
from collections.abc import Mapping, Sequence

import pytest
from markupsafe import Markup

from platzky.content_types import BUILTIN_CONTENT_TYPES, POST, ContentType
from platzky.plugin.content_transformer import (
    ContentTransformerPluginBase,
    ContentTransformerRegistry,
)
from platzky.shortcodes import (
    IntRange,
    ManyOf,
    OneOf,
    Shortcode,
    ShortcodeAttr,
    ShortcodeAttrs,
    ShortcodeError,
)
from platzky.shortcodes.constraints import ANY_TEXT


def _apply_shortcodes(content: str, shortcodes: dict[str, Shortcode]) -> str:
    """Parse content with these shortcodes registered, through a granted registry.

    ``Markup`` because these tests are about what a parser does with a post body, whose
    author vouched for it — an unvouched string is escaped and parsed leniently instead.
    """

    class _TestPlugin(ContentTransformerPluginBase):
        accepted_content_types: Mapping[ContentType, str] = dict.fromkeys(
            BUILTIN_CONTENT_TYPES, "Exercised by tests."
        )

    _TestPlugin.shortcodes = shortcodes
    plugin = _TestPlugin({})
    registry = ContentTransformerRegistry(BUILTIN_CONTENT_TYPES)
    registry.grant(plugin, frozenset({POST}))
    return registry.transform_content([plugin], Markup(content), POST)


def _sc(tag: str) -> Shortcode:
    """Build a minimal Shortcode for use in tests."""

    class _SC(Shortcode):
        name = tag
        description = "test"

        def render(
            self,
            attrs: ShortcodeAttrs,  # noqa: ARG002
            content: str,
            children: Sequence[Markup],  # noqa: ARG002
        ) -> str:
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
            def render(
                self,
                attrs: ShortcodeAttrs,
                content: str,
                children: Sequence[Markup],
            ) -> str: ...

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

    def test_invalid_kind_raises(self) -> None:
        """Caught at class definition, since a plugin author may not run a type checker."""

        def _render(_self: object, attrs: ShortcodeAttrs, content: str) -> str:
            return str(attrs) + content

        with pytest.raises(ValueError, match="declares `kind` 'Void'"):
            _ = type(
                "_BadKindSC",
                (Shortcode,),
                {"name": "ok", "description": "test", "kind": "Void", "render": _render},
            )

    def test_kind_defaults_to_block(self) -> None:
        assert _sc("anything").kind == "block"


def _echo_sc(tag: str, *attr_names: str) -> Shortcode:
    """Build a Shortcode whose render echoes the attrs and content it received."""

    class _SC(Shortcode):
        name = tag
        description = "test"
        attributes = ShortcodeAttrs([ShortcodeAttr(n, "desc") for n in attr_names])

        def render(
            self,
            attrs: ShortcodeAttrs,
            content: str,
            children: Sequence[Markup],  # noqa: ARG002
        ) -> str:
            return f"[{sorted(attrs.values.items())}|{content}]"

    return _SC()


class TestRenderField:
    def test_scalar_value_becomes_content(self) -> None:
        assert _echo_sc("mytag").render_value("SAVE20") == "[[]|SAVE20]"

    def test_dict_content_key_becomes_content(self) -> None:
        assert _echo_sc("mytag").render_value({"content": "SAVE20"}) == "[[]|SAVE20]"

    def test_dict_value_key_becomes_content(self) -> None:
        assert _echo_sc("mytag").render_value({"value": "SAVE20"}) == "[[]|SAVE20]"

    def test_declared_keys_become_attributes(self) -> None:
        sc = _echo_sc("mytag", "color")
        assert sc.render_value({"color": "red", "value": "X"}) == "[[('color', 'red')]|X]"

    def test_undeclared_keys_are_dropped(self) -> None:
        sc = _echo_sc("mytag", "color")
        assert sc.render_value({"unknown": "x", "value": "X"}) == "[[]|X]"

    def test_missing_content_renders_empty(self) -> None:
        assert _echo_sc("mytag").render_value({}) == "[[]|]"

    def test_none_content_renders_empty(self) -> None:
        assert _echo_sc("mytag").render_value({"value": None}) == "[[]|]"

    def test_content_key_declares_where_the_content_lives(self) -> None:
        class _SC(Shortcode):
            name = "mytag"
            description = "test"
            content_key = "code"

            def render(
                self,
                attrs: ShortcodeAttrs,  # noqa: ARG002
                content: str,
                children: Sequence[Markup],  # noqa: ARG002
            ) -> str:
                return f"[{content}]"

        assert _SC().render_value({"code": "SAVE20"}) == "[SAVE20]"

    def test_value_key_still_works_alongside_a_custom_content_key(self) -> None:
        class _SC(Shortcode):
            name = "mytag"
            description = "test"
            content_key = "code"

            def render(
                self,
                attrs: ShortcodeAttrs,  # noqa: ARG002
                content: str,
                children: Sequence[Markup],  # noqa: ARG002
            ) -> str:
                return f"[{content}]"

        assert _SC().render_value({"value": "SAVE20"}) == "[SAVE20]"

    def test_field_and_tag_rendering_are_the_same_html(self) -> None:
        sc = _echo_sc("mytag", "color")
        from_tag = sc.render(_attrs_with(sc, color="red"), Markup("X"), ())
        from_field = sc.render_value({"color": "red", "value": "X"})
        assert from_tag == from_field


def _attrs_with(sc: Shortcode, **values: str) -> ShortcodeAttrs:
    """Build the attrs a parsed tag would carry for this shortcode."""
    attrs = ShortcodeAttrs(list(sc.attributes))
    attrs.values = dict(values)
    return attrs


def _box_sc() -> Shortcode:
    """Build a shortcode with one constrained, defaulted attribute, echoing what render gets."""

    class _SC(Shortcode):
        name = "box"
        description = "test"
        attributes = ShortcodeAttrs(
            [ShortcodeAttr("size", "desc", default="10", constraints=IntRange(1, 99))]
        )

        def render(
            self,
            attrs: ShortcodeAttrs,
            content: str,
            children: Sequence[Markup],  # noqa: ARG002
        ) -> str:
            return f"[{attrs.size}|{content}]"

    return _SC()


class TestAttributeConstraints:
    def test_a_left_out_attribute_gets_its_default(self) -> None:
        assert _apply_shortcodes("[box]x[/box]", {"box": _box_sc()}) == "[10|x]"

    def test_an_empty_attribute_gets_its_default(self) -> None:
        assert _apply_shortcodes('[box size=""]x[/box]', {"box": _box_sc()}) == "[10|x]"

    def test_a_passing_value_reaches_render_as_written(self) -> None:
        assert _apply_shortcodes('[box size="07"]x[/box]', {"box": _box_sc()}) == "[07|x]"

    def test_any_container_of_strings_works_as_constraints(self) -> None:
        class _SC(Shortcode):
            name = "tone"
            description = "test"
            attributes = ShortcodeAttrs(
                [ShortcodeAttr("level", "desc", constraints=frozenset({"low"}))]
            )

            def render(
                self,
                attrs: ShortcodeAttrs,
                content: str,
                children: Sequence[Markup],  # noqa: ARG002
            ) -> str:
                return f"[{attrs.level}|{content}]"

        assert _SC().render_value({"level": "low", "value": "x"}) == "[low|x]"
        assert _SC().render_value({"level": "high", "value": "x"}) == ""

    def test_a_refused_value_drops_only_its_own_tag(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            result = _apply_shortcodes('a [box size="big"]x[/box] b', {"box": _box_sc()})

        assert result == "a  b"
        expected = "[box] rendered nothing: size 'big' is not a whole number from 1 to 99"
        assert expected in caplog.text

    def test_a_stored_value_is_parsed_the_same_way(self) -> None:
        sc = _box_sc()
        assert sc.render_value({"size": "7", "value": "x"}) == "[7|x]"
        assert sc.render_value({"size": "big", "value": "x"}) == ""

    def test_accepting_leaves_the_declared_schema_untouched(self) -> None:
        sc = _box_sc()
        assert sc.attributes.accept({"size": "5"}) == {"size": "5"}
        assert sc.attributes.values == {}


class TestIntRange:
    @pytest.mark.parametrize("value", ["1", "07", "99"])
    def test_takes_bare_digits_within_range(self, value: str) -> None:
        assert value in IntRange(1, 99)

    @pytest.mark.parametrize("value", ["0", "100", "seven", "7.5", "", " 7", "+7", "7_0", "²"])
    def test_takes_nothing_else(self, value: str) -> None:
        """Nothing is rewritten on the way, so a sign, space or separator is refused."""
        assert value not in IntRange(1, 99)

    def test_an_open_upper_bound_takes_any_larger_number(self) -> None:
        assert "123456" in IntRange(1)

    def test_describes_what_it_takes(self) -> None:
        assert str(IntRange(1, 99)) == "a whole number from 1 to 99"
        assert str(IntRange(1)) == "a whole number, at least 1"


class TestOneOf:
    def test_takes_a_declared_word(self) -> None:
        assert "full" in OneOf("fit", "full")

    @pytest.mark.parametrize("value", ["wide", "FULL", " full"])
    def test_takes_nothing_else(self, value: str) -> None:
        assert value not in OneOf("fit", "full")

    def test_describes_its_choices_in_declared_order(self) -> None:
        assert str(OneOf("info", "warning", "danger")) == "one of info, warning, danger"


class TestManyOf:
    @pytest.mark.parametrize("value", ["sponsored", "sponsored nofollow", "ugc  sponsored"])
    def test_takes_any_run_of_declared_words(self, value: str) -> None:
        assert value in ManyOf("sponsored", "nofollow", "ugc")

    @pytest.mark.parametrize("value", ["evil", "sponsored evil", "SPONSORED"])
    def test_refuses_the_whole_value_for_one_unknown_word(self, value: str) -> None:
        assert value not in ManyOf("sponsored", "nofollow", "ugc")

    def test_describes_its_choices_in_declared_order(self) -> None:
        assert str(ManyOf("sponsored", "nofollow")) == "words from sponsored, nofollow"


class TestAnyText:
    def test_takes_anything_and_says_nothing(self) -> None:
        assert "anything at all" in ANY_TEXT
        assert str(ANY_TEXT) == ""


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
            kind = "void"

            def render(
                self,
                attrs: ShortcodeAttrs,
                content: str,
                children: Sequence[Markup],  # noqa: ARG002
            ) -> str:
                calls.append((attrs, content))
                return "<img>"

        _apply_shortcodes('[img url="x.jpg"]', {"img": _ImgSC()})
        assert calls == [({"url": "x.jpg"}, "")]

    def test_attrs_parsed_into_dict(self) -> None:
        received: list[ShortcodeAttrs] = []

        class _FooSC(Shortcode):
            name = "foo"
            description = "test"

            def render(
                self,
                attrs: ShortcodeAttrs,
                content: str,  # noqa: ARG002
                children: Sequence[Markup],  # noqa: ARG002
            ) -> str:
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


class TestTagMatching:
    """Tags pair by stack, not by proximity."""

    def test_tag_nests_inside_another_of_the_same_name(self) -> None:
        sc = _sc("box")
        result = _apply_shortcodes("[box][box]a[/box][/box]", {"box": sc})
        assert result == "[RENDERED:box:[RENDERED:box:a]]"

    def test_same_tag_nests_three_deep(self) -> None:
        sc = _sc("box")
        result = _apply_shortcodes("[box][box][box]x[/box][/box][/box]", {"box": sc})
        assert result == "[RENDERED:box:[RENDERED:box:[RENDERED:box:x]]]"

    def test_closing_tag_with_nothing_open_is_rejected(self) -> None:
        sc = _sc("box")
        with pytest.raises(ShortcodeError, match=r"\[/box\] closes nothing"):
            _apply_shortcodes("a[/box]", {"box": sc})

    def test_closing_a_void_tag_says_it_takes_no_closing_tag(self) -> None:
        """The mistake is not a missing opener, so saying so would send them the wrong way."""

        class _ImgSC(Shortcode):
            name = "img"
            description = "test"
            kind = "void"

            def render(
                self,
                attrs: ShortcodeAttrs,  # noqa: ARG002
                content: str,  # noqa: ARG002
                children: Sequence[Markup],  # noqa: ARG002
            ) -> str:
                return "<img>"

        shortcodes: dict[str, Shortcode] = {"img": _ImgSC()}

        with pytest.raises(ShortcodeError, match="takes no closing tag"):
            _apply_shortcodes("[img][/img]", shortcodes)

    def test_unregistered_closing_tag_is_still_left_alone(self) -> None:
        """Platzky has no opinion on a name it does not know, closing tag or not."""
        sc = _sc("box")
        assert _apply_shortcodes("a[/unknown]", {"box": sc}) == "a[/unknown]"

    def test_unclosed_block_tag_is_rejected(self) -> None:
        """A block tag owes a closing tag; without one there is nothing correct to render."""
        sc = _sc("box")
        with pytest.raises(ShortcodeError, match=r"\[box\] is never closed"):
            _apply_shortcodes("[box]a", {"box": sc})

    def test_unclosed_tag_error_names_the_tag_and_where_it_was_written(self) -> None:
        """A failed render leaves only the log, so it has to say which bracket was wrong."""
        sc = _sc("box")
        with pytest.raises(ShortcodeError) as excinfo:
            _apply_shortcodes("hello [box]a", {"box": sc})

        assert excinfo.value.tag == "box"
        assert excinfo.value.position == 6
        assert "character 6" in str(excinfo.value)

    def test_crossed_tags_are_rejected(self) -> None:
        """``[box][b]x[/box]`` leaves ``[b]`` unclosed, whatever the author intended."""
        outer, inner = _sc("box"), _sc("b")
        with pytest.raises(ShortcodeError, match=r"\[b\] is never closed"):
            _apply_shortcodes("[box][b]x[/box]", {"box": outer, "b": inner})

    def test_void_tag_needs_no_closing_tag(self) -> None:
        class _ImgSC(Shortcode):
            name = "img"
            description = "test"
            kind = "void"

            def render(
                self,
                attrs: ShortcodeAttrs,  # noqa: ARG002
                content: str,  # noqa: ARG002
                children: Sequence[Markup],  # noqa: ARG002
            ) -> str:
                return "<img>"

        assert _apply_shortcodes("a [img] b", {"img": _ImgSC()}) == "a <img> b"

    def test_void_tag_does_not_swallow_what_follows_it(self) -> None:
        """The old parser opened a frame for every tag; a void one must not."""

        class _ImgSC(Shortcode):
            name = "img"
            description = "test"
            kind = "void"

            def render(
                self,
                attrs: ShortcodeAttrs,  # noqa: ARG002
                content: str,  # noqa: ARG002
                children: Sequence[Markup],  # noqa: ARG002
            ) -> str:
                return "<img>"

        block = _sc("box")
        result = _apply_shortcodes("[box][img]tail[/box]", {"img": _ImgSC(), "box": block})
        assert result == "[RENDERED:box:<img>tail]"


def _raw_sc(tag: str) -> Shortcode:
    """Build a raw shortcode that echoes its body untouched."""

    class _SC(Shortcode):
        name = tag
        description = "test"
        kind = "raw"

        def render(
            self,
            attrs: ShortcodeAttrs,  # noqa: ARG002
            content: str,
            children: Sequence[Markup],  # noqa: ARG002
        ) -> str:
            return f"[RAW:{content}]"

    return _SC()


class TestRawKind:
    """A raw body is text, not syntax."""

    def test_body_is_passed_through_untouched(self) -> None:
        assert _apply_shortcodes("[raw]hello[/raw]", {"raw": _raw_sc("raw")}) == "[RAW:hello]"

    def test_shortcodes_inside_a_raw_body_are_not_parsed(self) -> None:
        raw, block = _raw_sc("raw"), _sc("box")
        result = _apply_shortcodes("[raw][box]x[/box][/raw]", {"raw": raw, "box": block})
        assert result == "[RAW:[box]x[/box]]"

    def test_an_unclosed_tag_inside_a_raw_body_is_not_an_error(self) -> None:
        """Nothing in there is a tag, so there is nothing to be unclosed."""
        raw, block = _raw_sc("raw"), _sc("box")
        assert _apply_shortcodes("[raw][box][/raw]", {"raw": raw, "box": block}) == "[RAW:[box]]"

    def test_parsing_resumes_after_the_raw_body(self) -> None:
        raw, block = _raw_sc("raw"), _sc("box")
        result = _apply_shortcodes("[raw][x][/raw][box]y[/box]", {"raw": raw, "box": block})
        assert result == "[RAW:[x]][RENDERED:box:y]"

    def test_unclosed_raw_tag_is_rejected(self) -> None:
        shortcodes = {"raw": _raw_sc("raw")}

        with pytest.raises(ShortcodeError, match=r"\[raw\] is never closed"):
            _apply_shortcodes("[raw]forever", shortcodes)

    def test_longer_tag_name_is_not_shadowed_by_a_shorter_prefix(self) -> None:
        short, long = _sc("box"), _sc("boxed")
        result = _apply_shortcodes("[boxed]q[/boxed]", {"box": short, "boxed": long})
        assert result == "[RENDERED:boxed:q]"
