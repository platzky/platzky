"""Tests for ContentTransformerRegistry — the content-transformer routing gate.

These need no Flask app: the registry holds the allowlist and the vocabulary itself and
takes the plugins on dispatch, so the routing rules are exercised directly.
"""

import logging
from typing import ClassVar

import pytest

from platzky.content_types import BUILTIN_CONTENT_TYPES, ContentType
from platzky.plugin.content_transformer import (
    ContentTransformerPluginBase,
    ContentTransformerRegistry,
)
from platzky.shortcodes import Shortcode, ShortcodeAttrs


class _ShoutShortcode(Shortcode):
    name = "shout"
    description = "Upper-case content."

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Return content in upper case."""
        return content.upper()


class ShoutPlugin(ContentTransformerPluginBase):
    """Accepts every builtin content type and registers [shout]."""

    accepted_content_types: frozenset[ContentType] = BUILTIN_CONTENT_TYPES
    shortcodes: ClassVar[dict[str, Shortcode]] = {"shout": _ShoutShortcode()}


class PostOnlyPlugin(ContentTransformerPluginBase):
    """Accepts posts only, and registers the same tag name as ShoutPlugin."""

    accepted_content_types: frozenset[ContentType] = frozenset({"post"})
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
        plugin.accepted_content_types = BUILTIN_CONTENT_TYPES

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
        """Two permitted plugins claiming a tag name warn, and the last one wins."""
        first, second = ShoutPlugin({}), PostOnlyPlugin({})
        registry.grant(first, frozenset({"post"}))
        registry.grant(second, frozenset({"post"}))

        with caplog.at_level(logging.WARNING):
            result = registry.shortcodes_for([first, second], "post")

        assert result["shout"] is second.shortcodes["shout"]
        assert "overrides an existing registration" in caplog.text


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
