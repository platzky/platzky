"""ContentTransformerPluginBase capability — plugins that transform content."""

from __future__ import annotations

import logging
import re
from abc import ABC
from collections.abc import Iterable
from itertools import zip_longest
from typing import ClassVar, final

import jinja2.ext
from markupsafe import escape

from platzky.content_types import ContentType
from platzky.plugin.plugin import PluginBase
from platzky.plugin.plugin_config import PluginConfigBase
from platzky.shortcodes import Shortcode, ShortcodeAttrs


class ContentTransformerPluginConfig(PluginConfigBase):
    """Plugin config for ContentTransformerPluginBase — carries the content-type allowlist."""

    allowed_content_types: frozenset[ContentType] = frozenset()


logger = logging.getLogger(__name__)

_SHORTCODE_TAG_RE = re.compile(r"\[[^\]]*\]|<[^>]*>")

_MAX_ATTR_NAME_LEN = 100
_MAX_ATTR_VALUE_LEN = 2048
_ATTR_RE = re.compile(rf'([\w-]{{1,{_MAX_ATTR_NAME_LEN}}})="([^"]{{0,{_MAX_ATTR_VALUE_LEN}}})"')


def _apply_shortcodes(content: str, shortcodes: dict[str, Shortcode]) -> str:
    if not shortcodes:
        return content

    tag_names = "|".join(re.escape(n) for n in shortcodes)
    pattern = re.compile(
        rf"\[({tag_names})((?:\s+[\w-]+=\"[^\"]*\")*)\s*\](?:(.*?)\[/\1\])?",
        re.DOTALL,
    )

    def _apply(text: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            sc = shortcodes[m.group(1)]
            attrs = ShortcodeAttrs(list(sc.attributes))
            attrs.values = dict(_ATTR_RE.findall(m.group(2) or ""))
            inner = m.group(3) or ""
            if inner:
                inner = _apply(inner)
            return sc.render(attrs, inner)

        return pattern.sub(_replace, text)

    return _apply(content)


class ContentTransformerPluginBase(PluginBase, ABC):
    """Base class for content-transformer plugins.

    Subclasses declare which content types they want to transform via
    ``accepted_content_types``. A plugin may name a kind of content some other package
    brings — accepting one never means importing that package — and still install on an
    application that has no such content, where it is simply never called. To *bring* a
    content type, see ``PluginBase.provides_content_types``. The engine enforces final
    routing — ``Engine.may_transform`` decides, not the plugin, so widening
    ``accepted_content_types`` cannot widen the operator's grant.

    Declare ``shortcodes`` to register shortcode tags; they are applied
    automatically by ``transform_content``. An application rendering a *stored value*
    through ``Shortcode.render_value`` bypasses ``transform_content`` entirely, so it
    must take its shortcodes from ``Engine.shortcodes_for`` to stay behind the same
    gate rather than reading ``shortcodes`` off loaded plugins itself.

    Override ``transform_text`` to
    apply plain-text transformations — the framework guarantees that
    ``transform_text`` is never called with shortcode tag markup so
    transformations cannot accidentally mangle tags intended for other plugins.
    """

    accepted_content_types: frozenset[ContentType] = frozenset()
    shortcodes: ClassVar[dict[str, Shortcode]] = {}

    @final
    def transform_content(self, content: str) -> str:
        """Split content on shortcode tags, transform plain-text segments, then apply shortcodes.

        Not overridable — override ``transform_text`` instead.

        Args:
            content: Raw content string to transform.

        Returns:
            Transformed content string.
        """
        parts = _SHORTCODE_TAG_RE.split(content)
        tags = _SHORTCODE_TAG_RE.findall(content)
        transformed = [self.transform_text(p) for p in parts]
        reassembled = "".join(
            segment for pair in zip_longest(transformed, tags, fillvalue="") for segment in pair
        )
        return _apply_shortcodes(reassembled, self.shortcodes)

    def transform_text(self, text: str) -> str:
        """Apply plain-text transformation to a non-tag content segment.

        Override this to transform plain text while the framework ensures
        shortcode tags are never passed here.

        Args:
            text: Plain-text segment (no shortcode tag markup).

        Returns:
            Transformed text.
        """
        return text

    def get_jinja_extensions(self) -> list[type[jinja2.ext.Extension]]:
        """Return Jinja2 extension classes to register with the template engine.

        Returns:
            Jinja2 extension classes to register; empty list by default.
        """
        return []


class ContentTransformerRegistry:
    """The gate deciding which content transformers may act on which content.

    Holds the content-type vocabulary transformers route on and each plugin's
    operator-granted allowlist, and applies both when dispatching. Kept apart from the
    engine so the routing rules sit beside the capability base they govern and the
    config model that defines the grant, and so they can be exercised without an app.

    What it does not own is which transformers exist and in what order: ``Engine.plugins``
    is that, uniformly for every capability, and the list arrives as a dispatch argument.
    Three things keep it there. Transformers chain, so their order is semantic, and it is
    set in two places — ``register_plugin`` appends, while ``platzky.py`` inserts the
    builtin shortcodes at index 0 to run ahead of any plugin filter. One instance may
    implement several capabilities and is registered under each, so only the engine sees
    the whole picture. And applications add capability bases of their own through
    ``extra_plugin_bases``, which ``register_plugin`` covers generically; a capability
    owning its plugins would be a second registration path that mechanism misses.

    It does hold a reference to every granted plugin, since the allowlist is keyed by
    instance — membership and order are what live elsewhere, not the plugins themselves.
    """

    def __init__(self, known_content_types: Iterable[ContentType] = ()) -> None:
        """Initialise the gate.

        Args:
            known_content_types: The vocabulary in place before any plugin loads —
                platzky's builtins plus whatever the application registers.
        """
        self.known_content_types: set[ContentType] = set(known_content_types)
        self._allowlist: dict[ContentTransformerPluginBase, frozenset[ContentType]] = {}
        self._pending_grants: list[tuple[str, frozenset[ContentType]]] = []

    def grant(
        self, plugin: ContentTransformerPluginBase, allowed_types: frozenset[ContentType]
    ) -> None:
        """Record the operator's grant for a plugin.

        One call because it is one decision: the same grant is what ``may_transform``
        enforces and what ``warn_unknown_grants`` later checks for typos. An empty
        frozenset blocks every content type, as does never granting a plugin at all.
        Called by the plugin loader; not intended to be called from plugin code.

        Args:
            plugin: The plugin the grant applies to. Its ``name`` identifies it in any
                later warning, so grant it after ``Engine.register_plugin`` has stamped
                that on.
            allowed_types: Content types the operator granted it.
        """
        self._allowlist[plugin] = allowed_types
        self._pending_grants.append((plugin.name, allowed_types))

    def may_transform(
        self, plugin: ContentTransformerPluginBase, content_type: ContentType
    ) -> bool:
        """Return whether this plugin may act on this kind of content.

        Both keys must turn: the plugin's own ``accepted_content_types`` declaration and
        the operator's grant. The allowlist lives here and a plugin never receives it, so
        widening ``accepted_content_types`` at runtime opens the first key and not the
        second. Default-deny: an unlisted plugin is blocked, as is an empty grant.

        Args:
            plugin: The content-transformer plugin to check.
            content_type: The kind of content it wants to act on.

        Returns:
            True if the plugin is both willing and permitted.
        """
        if content_type not in plugin.accepted_content_types:
            return False
        return content_type in self._allowlist.get(plugin, frozenset())

    def transform_content(
        self,
        plugins: Iterable[ContentTransformerPluginBase],
        content: str,
        content_type: ContentType,
    ) -> str:
        """Run every permitted transformer over the content, in order.

        Transformers chain their output, so a failing transformer aborts the chain rather
        than silently passing partial output to the next stage.

        Content is escaped on the way in unless the caller vouched for it by passing
        ``Markup`` — the caller is the only party that knows where it came from, so the
        default is the safe one and vouching is the deliberate act. Everything the
        pipeline adds afterwards is markup platzky itself produced, by plugins that turned
        both keys for this content type, so it is trusted by construction and shortcodes
        embed their content directly. See ``Shortcode.render``.

        Args:
            plugins: Content transformers in registration order.
            content: The content to transform. A plain ``str`` is treated as untrusted and
                escaped; a ``Markup`` is taken as vouched for and passed through.
            content_type: The kind of content, e.g. ``POST``.

        Returns:
            The content after every permitted transformer has run.
        """
        # escape() is a no-op on anything carrying __html__, so this is the whole rule.
        # It makes content safe; it does not stop shortcode parsing. Brackets survive, so
        # a bare tag in untrusted content still fires — harmlessly, since what it wraps is
        # already escaped — while a quoted attribute does not survive and that tag renders
        # literally. Safety does not depend on which happens.
        content = str(escape(content))
        for plugin in plugins:
            if not self.may_transform(plugin, content_type):
                continue
            content = plugin.transform_content(content)
        return content

    def shortcodes_for(
        self, plugins: Iterable[ContentTransformerPluginBase], content_type: ContentType
    ) -> dict[str, Shortcode]:
        """Return the shortcodes permitted to render this kind of content.

        The gate an application needs when it renders a *stored value* through
        ``Shortcode.render_value`` instead of transforming prose. That call does not pass
        through ``transform_content``, so an application collecting shortcodes off its
        loaded plugins itself would honour neither the plugin's declaration nor the
        operator's grant — the grant would silently govern nothing.

        Args:
            plugins: Content transformers in registration order.
            content_type: The kind of content the shortcodes will render.

        Returns:
            Permitted shortcodes keyed by tag name. A name registered by more than one
            permitted plugin is taken from the last, matching startup registration.
        """
        permitted: dict[str, Shortcode] = {}
        for plugin in plugins:
            if not self.may_transform(plugin, content_type):
                continue
            for tag_name, shortcode in plugin.shortcodes.items():
                if tag_name in permitted:
                    logger.warning(
                        "Plugin %s shortcode %r overrides an existing registration for "
                        "content type '%s'.",
                        type(plugin).__name__,
                        tag_name,
                        content_type,
                    )
                permitted[tag_name] = shortcode
        return permitted

    def warn_unknown_grants(self) -> None:
        """Warn about granted content types no plugin or application ever registered.

        The vocabulary is open, so an unknown type cannot be rejected: an application
        registers its own, and a plugin may name one this application does not have — a
        plugin built for another application installs cleanly and stays inert, which is
        deliberate. A grant naming a type nothing produces is almost always a typo in
        operator config, though, and silently grants nothing, so say so rather than
        leaving a transformer mysteriously idle.

        Called by the plugin loader once every plugin is loaded, so that a plugin
        contributing a content type need not load before the plugins granted it.
        """
        for plugin_name, allowed in self._pending_grants:
            for unknown in sorted(allowed - self.known_content_types):
                logger.warning(
                    "Plugin %s is granted content type '%s', which this application does not "
                    "produce; the grant has no effect. Known types: %s",
                    plugin_name,
                    unknown,
                    ", ".join(sorted(self.known_content_types)),
                )
        self._pending_grants.clear()
