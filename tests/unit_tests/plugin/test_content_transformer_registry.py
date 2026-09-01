"""Tests for ContentTransformerRegistry — the content-transformer routing gate.

These need no Flask app: the registry holds the allowlist and the vocabulary itself and
takes the plugins on dispatch, so the routing rules are exercised directly.
"""

import logging
from collections.abc import Mapping
from typing import ClassVar

import pytest
from markupsafe import Markup, escape

from platzky.content_types import ALL_CONTENT_TYPES, BUILTIN_CONTENT_TYPES, ContentType
from platzky.plugin.content_transformer import (
    ContentTransformerPluginBase,
    ContentTransformerRegistry,
)
from platzky.shortcodes import Shortcode, ShortcodeAttr, ShortcodeAttrs, ShortcodeError


class _ShoutShortcode(Shortcode):
    name = "shout"
    description = "Upper-case content."

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Return content in upper case."""
        return content.upper()


class ShoutPlugin(ContentTransformerPluginBase):
    """Accepts every builtin content type and registers [shout]."""

    accepted_content_types: Mapping[ContentType, str] = dict.fromkeys(
        BUILTIN_CONTENT_TYPES, "Exercised by tests."
    )
    shortcodes: ClassVar[dict[str, Shortcode]] = {"shout": _ShoutShortcode()}


class PostOnlyPlugin(ContentTransformerPluginBase):
    """Accepts posts only, and registers the same tag name as ShoutPlugin."""

    accepted_content_types: Mapping[ContentType, str] = {"post": "Exercised by tests."}
    shortcodes: ClassVar[dict[str, Shortcode]] = {"shout": _ShoutShortcode()}


class _WrapShortcode(Shortcode):
    name = "wrap"
    description = "Wrap content, taking an attribute."
    attributes: ClassVar[ShortcodeAttrs] = ShortcodeAttrs(
        [ShortcodeAttr("tone", "Tone of voice", required=False)]
    )

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:
        """Wrap content in a span carrying the tone."""
        return f'<span class="{escape(attrs.tone)}">{content}</span>'


class AttrPlugin(ContentTransformerPluginBase):
    """Registers a shortcode that takes a quoted attribute."""

    accepted_content_types: Mapping[ContentType, str] = dict.fromkeys(
        BUILTIN_CONTENT_TYPES, "Exercised by tests."
    )
    shortcodes: ClassVar[dict[str, Shortcode]] = {"wrap": _WrapShortcode()}


class AnyPlugin(ContentTransformerPluginBase):
    """Declares no constraint on where it runs."""

    accepted_content_types: Mapping[ContentType, str] = {ALL_CONTENT_TYPES: "No constraint."}
    shortcodes: ClassVar[dict[str, Shortcode]] = {"shout": _ShoutShortcode()}


@pytest.fixture
def registry() -> ContentTransformerRegistry:
    return ContentTransformerRegistry(BUILTIN_CONTENT_TYPES)


def _named_plugin(name: str) -> ShoutPlugin:
    """A plugin carrying the name the loader would have stamped on it."""
    plugin = ShoutPlugin({})
    plugin.name = name
    return plugin


class TestMayTransform:
    def test_both_keys_open(self, registry: ContentTransformerRegistry) -> None:
        """Willing plugin plus operator grant means permitted."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        assert registry.may_transform(plugin, "post")

    def test_grant_cannot_be_widened_by_the_plugin(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """A plugin widening its own declaration does not widen the operator's grant."""
        plugin = PostOnlyPlugin({})
        registry.grant(plugin, frozenset({"post"}))
        plugin.accepted_content_types = dict.fromkeys(BUILTIN_CONTENT_TYPES, "Exercised by tests.")

        assert not registry.may_transform(plugin, "page")

    def test_grant_wider_than_declaration_still_blocked(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """An operator cannot make a plugin handle content it never declared."""
        plugin = PostOnlyPlugin({})
        registry.grant(plugin, BUILTIN_CONTENT_TYPES)

        assert not registry.may_transform(plugin, "page")

    def test_unlisted_plugin_is_blocked(self, registry: ContentTransformerRegistry) -> None:
        """Default-deny: a plugin the loader never granted is blocked."""
        assert not registry.may_transform(ShoutPlugin({}), "post")

    def test_empty_grant_blocks_everything(self, registry: ContentTransformerRegistry) -> None:
        """An explicit empty grant blocks every content type."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset())

        assert not registry.may_transform(plugin, "post")


class TestRationaleIsRequired:
    """A declaration that asks for a content type must say why."""

    def test_missing_reason_is_rejected_at_class_definition(self) -> None:
        """Caught when the class is written, not when an operator wonders what to tick."""
        with pytest.raises(ValueError, match="needs a reason"):

            class NoReason(ContentTransformerPluginBase):
                accepted_content_types: Mapping[ContentType, str] = {"post": ""}

    def test_a_set_is_rejected(self) -> None:
        """The old frozenset shape carries no reasons, so it is not silently accepted."""
        with pytest.raises(ValueError, match="must map each content type"):

            class StillASet(ContentTransformerPluginBase):
                accepted_content_types = frozenset({"post"})  # type: ignore[assignment]

    def test_wildcard_needs_a_reason_too(self) -> None:
        """Claiming no constraint is still a claim an operator deserves to see justified."""
        with pytest.raises(ValueError, match="ALL_CONTENT_TYPES"):

            class BlankWildcard(ContentTransformerPluginBase):
                accepted_content_types: Mapping[ContentType, str] = {ALL_CONTENT_TYPES: "  "}

    def test_declaring_nothing_is_allowed(self) -> None:
        """A plugin that transforms text only asks for nothing and explains nothing."""

        class TextOnly(ContentTransformerPluginBase):
            pass

        assert TextOnly({}).accepted_content_types == {}


class TestRationale:
    def test_enumerated_plugin_gives_a_reason_per_type(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """Each checkbox carries the reason its own type was asked for."""
        assert registry.rationale_for(PostOnlyPlugin({}), "post") == "Exercised by tests."
        assert registry.rationale_for(PostOnlyPlugin({}), "page") == ""

    def test_wildcard_reason_stands_for_every_offered_type(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """One claim, so one reason, shown against each type it is offered."""
        plugin = AnyPlugin({})

        assert registry.rationale_for(plugin, "post") == "No constraint."
        assert registry.rationale_for(plugin, "page") == "No constraint."
        assert registry.rationale_for(plugin, "not_a_known_type") == ""


class TestWildcard:
    """ALL_CONTENT_TYPES offers every known type; it grants none of them."""

    def test_offers_the_whole_vocabulary(self, registry: ContentTransformerRegistry) -> None:
        """The admin panel's checkboxes: everything the application knows about."""
        registry.known_content_types |= {"field"}

        assert registry.acceptable_content_types(AnyPlugin({})) == registry.known_content_types

    def test_resolves_lazily_so_load_order_does_not_matter(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """A type contributed by a plugin loaded later is still offered."""
        plugin = AnyPlugin({})
        before = set(registry.acceptable_content_types(plugin))

        registry.known_content_types |= {"catalogue_attr"}

        assert "catalogue_attr" not in before
        assert "catalogue_attr" in registry.acceptable_content_types(plugin)

    def test_accepting_everything_grants_nothing(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """Default-deny is untouched: the operator still names each type."""
        plugin = AnyPlugin({})

        assert not registry.may_transform(plugin, "post")

        registry.grant(plugin, frozenset({"post"}))

        assert registry.may_transform(plugin, "post")
        assert not registry.may_transform(plugin, "page")

    def test_grant_beyond_the_vocabulary_is_still_blocked(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """The wildcard means every *known* type, not every string an operator can type."""
        plugin = AnyPlugin({})
        registry.grant(plugin, frozenset({"typo_type"}))

        assert not registry.may_transform(plugin, "typo_type")

    def test_enumerating_plugin_is_unaffected(self, registry: ContentTransformerRegistry) -> None:
        """A plugin with a real constraint still offers only what it named."""
        assert registry.acceptable_content_types(PostOnlyPlugin({})) == frozenset({"post"})


class TestTrustBoundary:
    """Content is escaped on the way in unless the caller vouched with Markup."""

    def test_unvouched_content_is_escaped(self, registry: ContentTransformerRegistry) -> None:
        """The caller said nothing about where this came from, so it is not trusted."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        result = registry.transform_content([plugin], "<img src=x onerror=1>", "post")

        assert result == "&lt;img src=x onerror=1&gt;"

    def test_vouched_content_passes_through(self, registry: ContentTransformerRegistry) -> None:
        """Markup is the caller vouching, as blog.py does for an author's post body."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        result = registry.transform_content([plugin], Markup("<em>hi</em>"), "post")

        assert result == "<em>hi</em>"

    def test_unvouched_tag_without_attributes_still_fires(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """Escaping does not stop shortcode parsing — it only makes the content safe.

        Brackets are not escaped, so a bare tag in untrusted content still invokes the
        plugin. That is not a hole: whatever it renders was escaped on the way in.
        """
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        assert registry.transform_content([plugin], "[shout]hi[/shout]", "post") == "HI"

    def test_unvouched_tag_with_attributes_stops_parsing(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """A quoted attribute does not survive escaping, so the tag renders literally.

        An inconsistency worth knowing about rather than relying on: whether an untrusted
        tag fires depends on whether it carries attributes. Both outcomes are safe.
        """
        plugin = AttrPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        result = registry.transform_content([plugin], '[wrap tone="loud"]hi[/wrap]', "post")

        assert result == "[wrap tone=&#34;loud&#34;]hi[/wrap]"

    def test_a_stranger_cannot_fail_the_render_with_a_malformed_tag(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """Unvouched content is parsed leniently, and it has to be.

        Escaping mangles the tags on the way in: the quotes in ``[wrap tone="loud"]``
        become entities, so the opening tag stops matching while ``[/wrap]`` still does.
        Parsed strictly, that closing tag closes nothing and the page fails — which would
        let anyone who can write a comment take a page down by using a shortcode
        perfectly correctly.
        """
        plugin = AttrPlugin({})
        registry.grant(plugin, frozenset({"comment"}))
        registry.known_content_types |= {"comment"}

        for hostile in ['[wrap tone="loud"]hi[/wrap]', "[/wrap]", "[wrap]hi"]:
            assert registry.transform_content([plugin], hostile, "comment")

    def test_vouched_content_is_parsed_strictly(self, registry: ContentTransformerRegistry) -> None:
        """An author with write access can fix their own bracket, so they are told."""
        plugin = AttrPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        with pytest.raises(ShortcodeError):
            registry.transform_content([plugin], Markup("[wrap]hi"), "post")

    def test_vouched_shortcode_still_fires(self, registry: ContentTransformerRegistry) -> None:
        """The same tag in vouched content renders normally."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        assert registry.transform_content([plugin], Markup("[shout]hi[/shout]"), "post") == "HI"


class TestStripContentHtml:
    """STRIP_CONTENT_HTML overrules vouching, removing HTML the author wrote."""

    def test_off_by_default_so_vouched_html_still_renders(
        self, registry: ContentTransformerRegistry
    ) -> None:
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        assert registry.transform_content([plugin], Markup('a <img src="x">'), "post") == (
            'a <img src="x">'
        )

    def test_on_removes_the_tag_and_keeps_the_text(
        self, registry: ContentTransformerRegistry
    ) -> None:
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        result = registry.transform_content(
            [plugin], Markup('a <b>bold</b> and <img src="x">'), "post", strip_html=True
        )

        assert result == "a bold and "

    def test_removals_are_logged(
        self, registry: ContentTransformerRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Stripping is lossy, so it must not be silent."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        with caplog.at_level(logging.WARNING):
            registry.transform_content(
                [plugin], Markup('<b>x</b> <img src="y">'), "post", strip_html=True
            )

        assert "Removed 2 HTML tag(s) from post content" in caplog.text
        assert "b, img" in caplog.text

    def test_nothing_is_logged_when_there_was_no_html(
        self, registry: ContentTransformerRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        with caplog.at_level(logging.WARNING):
            registry.transform_content([plugin], Markup("just words"), "post", strip_html=True)

        assert "Removed" not in caplog.text

    def test_a_quote_containing_an_angle_bracket_does_not_leak(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """``>`` is legal inside an attribute; a regex would leave half the tag behind."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        result = registry.transform_content(
            [plugin], Markup('<img alt="a > b" src="/a.png">clean'), "post", strip_html=True
        )

        assert result == "clean"

    def test_shortcodes_keep_working_when_it_is_on(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """Escaping authored HTML must not disable the formatting meant to replace it."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        result = registry.transform_content(
            [plugin], Markup("[shout]hi[/shout]"), "post", strip_html=True
        )

        assert result == "HI"

    def test_shortcodes_with_attributes_keep_working_when_it_is_on(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """The case a bare tag does not cover: ``escape()`` would eat the quotes.

        Turning quoted attributes into entities stops the tag matching, which would leave
        every attributed shortcode as literal text — disabling the very formatting this
        flag exists to make authors use.
        """
        plugin = AttrPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        result = registry.transform_content(
            [plugin], Markup('[wrap tone="loud"]hi[/wrap]'), "post", strip_html=True
        )

        assert result == '<span class="loud">hi</span>'

    def test_html_around_a_shortcode_goes_while_the_shortcode_renders(
        self, registry: ContentTransformerRegistry
    ) -> None:
        plugin = AttrPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        result = registry.transform_content(
            [plugin], Markup('<b>x</b> [wrap tone="loud"]hi[/wrap]'), "post", strip_html=True
        )

        assert result == 'x <span class="loud">hi</span>'

    def test_untrusted_content_is_unaffected(self, registry: ContentTransformerRegistry) -> None:
        """It was escaped already; turning the flag on must not escape it twice."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        off = registry.transform_content([plugin], '<img src="x">', "post")
        on = registry.transform_content([plugin], '<img src="x">', "post", strip_html=True)

        assert off == on == "&lt;img src=&#34;x&#34;&gt;"


class TestDispatch:
    def test_transform_content_runs_only_permitted_plugins(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """Content passes untouched through a plugin that is not permitted."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        assert registry.transform_content([plugin], "[shout]hi[/shout]", "post") == "HI"
        assert (
            registry.transform_content([plugin], "[shout]hi[/shout]", "page") == "[shout]hi[/shout]"
        )

    def test_shortcodes_for_matches_may_transform(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """The value-rendering gate agrees with the prose gate."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        assert "shout" in registry.shortcodes_for([plugin], "post")
        assert registry.shortcodes_for([plugin], "page") == {}

    def test_shortcodes_for_warns_on_collision(
        self, registry: ContentTransformerRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Two permitted plugins claiming a tag name warn, and the first one wins."""
        first, second = ShoutPlugin({}), PostOnlyPlugin({})
        registry.grant(first, frozenset({"post"}))
        registry.grant(second, frozenset({"post"}))

        with caplog.at_level(logging.WARNING):
            result = registry.shortcodes_for([first, second], "post")

        assert result["shout"] is first.shortcodes["shout"]
        assert "already registered by" in caplog.text

    def test_collision_resolves_the_same_way_for_prose_and_stored_values(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """A contested tag renders identically whether written in prose or stored.

        Prose has no choice: transformers run in order and the first to own a tag consumes
        it, so a later plugin never sees it. ``shortcodes_for`` has to agree, or the same
        promo code renders one way in a post body and another against a record. The two
        plugins must render *differently* for this to test anything.
        """

        def plugin_rendering(marker: str) -> ContentTransformerPluginBase:
            class _SC(Shortcode):
                name = "promo"
                description = "Exercised by tests."

                def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
                    """Wrap content in a marker identifying which plugin rendered it."""
                    return f"<{marker}>{content}</{marker}>"

            class _P(ContentTransformerPluginBase):
                """Registers [promo] with an owner-specific rendering."""

                accepted_content_types: Mapping[ContentType, str] = {"post": "Tests."}
                shortcodes: ClassVar[dict[str, Shortcode]] = {"promo": _SC()}

            return _P({})

        first, second = plugin_rendering("alpha"), plugin_rendering("beta")
        registry.grant(first, frozenset({"post"}))
        registry.grant(second, frozenset({"post"}))

        from_prose = registry.transform_content([first, second], "[promo]X[/promo]", "post")
        from_value = registry.shortcodes_for([first, second], "post")["promo"].render_value("X")

        assert from_prose == "<alpha>X</alpha>"
        assert from_value == from_prose


class TestGrantReporting:
    def test_unknown_grant_is_warned_about(
        self, registry: ContentTransformerRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A grant naming a type nothing registered warns rather than failing silently."""
        registry.grant(_named_plugin("mapplugin"), frozenset({"field"}))

        with caplog.at_level(logging.WARNING):
            registry.warn_unknown_grants()

        assert "field" in caplog.text
        assert "has no effect" in caplog.text

    def test_grant_known_only_after_a_plugin_contributes_it(
        self, registry: ContentTransformerRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Load order does not matter: the type may arrive after the grant was recorded."""
        registry.grant(_named_plugin("mapplugin"), frozenset({"field"}))
        registry.known_content_types |= {"field"}

        with caplog.at_level(logging.WARNING):
            registry.warn_unknown_grants()

        assert caplog.text == ""

    def test_warning_is_not_repeated(
        self, registry: ContentTransformerRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A grant is warned about once, not again on every later call."""
        registry.grant(_named_plugin("mapplugin"), frozenset({"field"}))
        registry.warn_unknown_grants()
        caplog.clear()

        with caplog.at_level(logging.WARNING):
            registry.warn_unknown_grants()

        assert caplog.text == ""


class _CodeShortcode(Shortcode):
    name = "code"
    kind = "raw"
    description = "Show content without parsing it."

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Wrap the verbatim body in a pre block."""
        return f"<pre>{content}</pre>"


class CodePlugin(ContentTransformerPluginBase):
    """Registers a raw shortcode."""

    accepted_content_types: Mapping[ContentType, str] = dict.fromkeys(
        BUILTIN_CONTENT_TYPES, "Exercised by tests."
    )
    shortcodes: ClassVar[dict[str, Shortcode]] = {"code": _CodeShortcode()}


class _LetterAPlugin(ContentTransformerPluginBase):
    """Colours every letter 'a', the way the red_letter example plugin does."""

    accepted_content_types: Mapping[ContentType, str] = dict.fromkeys(
        BUILTIN_CONTENT_TYPES, "Exercised by tests."
    )

    def transform_text(self, text: str) -> str:
        """Wrap each 'a' in a span."""
        return text.replace("a", "<i>a</i>")


class TestFiltersNeverSeeRenderedMarkup:
    """Parsing, filtering and rendering are three passes, in that order."""

    def test_a_filter_does_not_reach_an_earlier_shortcode_s_attributes(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """The bug that motivated separating the passes.

        ``[wrap]`` renders to a tag carrying a ``class`` attribute. Running plugins one
        after another over a flat string handed that markup to the next plugin's filter,
        which rewrote the letter 'a' inside ``class`` and corrupted the tag.
        """
        wrap, letters = AttrPlugin({}), _LetterAPlugin({})
        for plugin in (wrap, letters):
            registry.grant(plugin, frozenset({"post"}))

        result = registry.transform_content(
            [wrap, letters], Markup('[wrap tone="loud"]hi[/wrap] and a plan'), "post"
        )

        assert result == '<span class="loud">hi</span> <i>a</i>nd <i>a</i> pl<i>a</i>n'

    def test_a_raw_body_survives_another_plugin_entirely(
        self, registry: ContentTransformerRegistry
    ) -> None:
        """Neither that plugin's filter nor its shortcodes reach inside."""
        code, letters = CodePlugin({}), _LetterAPlugin({})
        for plugin in (code, letters):
            registry.grant(plugin, frozenset({"post"}))

        result = registry.transform_content(
            [code, letters], Markup("[code]a [wrap]x[/wrap][/code] a"), "post"
        )

        assert result == "<pre>a [wrap]x[/wrap]</pre> <i>a</i>"
