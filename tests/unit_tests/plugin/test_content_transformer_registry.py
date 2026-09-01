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
from platzky.shortcodes import Shortcode, ShortcodeAttr, ShortcodeAttrs


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

    def test_vouched_shortcode_still_fires(self, registry: ContentTransformerRegistry) -> None:
        """The same tag in vouched content renders normally."""
        plugin = ShoutPlugin({})
        registry.grant(plugin, frozenset({"post"}))

        assert registry.transform_content([plugin], Markup("[shout]hi[/shout]"), "post") == "HI"


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
