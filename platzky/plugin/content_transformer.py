"""ContentTransformerPluginBase capability — plugins that transform content."""

from __future__ import annotations

import logging
import re
from abc import ABC
from collections.abc import Iterable, Mapping
from itertools import zip_longest
from typing import ClassVar, cast, final

import jinja2.ext
from markupsafe import Markup, escape

from platzky.content_types import ALL_CONTENT_TYPES, ContentType
from platzky.plugin.plugin import PluginBase
from platzky.plugin.plugin_config import PluginConfigBase
from platzky.shortcodes import Shortcode, ShortcodeAttrs


class ContentTransformerPluginConfig(PluginConfigBase):
    """Plugin config for ContentTransformerPluginBase — carries the content-type allowlist."""

    allowed_content_types: frozenset[ContentType] = frozenset()


logger = logging.getLogger(__name__)


def _wildcard_reason(declared: Mapping[ContentType, str]) -> str | None:
    """Return the wildcard rationale if this declaration carries one, else None.

    Matched by identity, so a content type that happens to be named ``"*"`` is not
    mistaken for the sentinel.
    """
    for content_type, reason in declared.items():
        if content_type is ALL_CONTENT_TYPES:
            return reason
    return None


_SHORTCODE_TAG_RE = re.compile(r"\[[^\]]*\]|<[^>]*>")

_MAX_ATTR_NAME_LEN = 100
_MAX_ATTR_VALUE_LEN = 2048
_ATTR_RE = re.compile(rf'([\w-]{{1,{_MAX_ATTR_NAME_LEN}}})="([^"]{{0,{_MAX_ATTR_VALUE_LEN}}})"')


#: One frame of the parse stack: tag name, its raw attribute text, and the rendered
#: pieces collected inside it so far. The outermost frame is the document itself and
#: carries ``""`` as its name, which no shortcode can have.
_Frame = tuple[str, str, list[str]]


def _tag_pattern(shortcodes: dict[str, Shortcode]) -> re.Pattern[str]:
    """Build the token pattern matching an opening or closing tag of a known shortcode.

    Names are alternated longest-first so a shortcode never shadows a longer one that
    starts with the same letters.

    Args:
        shortcodes: Registered shortcodes, keyed by tag name.

    Returns:
        A pattern whose groups are (closing name, opening name, opening attributes).
    """
    names = "|".join(re.escape(n) for n in sorted(shortcodes, key=len, reverse=True))
    return re.compile(rf"\[/({names})\]" rf"|\[({names})((?:\s+[\w-]+=\"[^\"]*\")*)\s*\]")


def _render_tag(shortcode: Shortcode, raw_attrs: str, inner: str) -> str:
    """Render one shortcode with its parsed attributes and already-rendered content.

    Args:
        shortcode: The shortcode to render.
        raw_attrs: The attribute text as written in the tag.
        inner: Content between the tags, with any nested shortcodes already rendered.

    Returns:
        The shortcode's replacement HTML.
    """
    attrs = ShortcodeAttrs(list(shortcode.attributes))
    attrs.values = dict(_ATTR_RE.findall(raw_attrs))
    # Markup, and truthfully: by here the content was either vouched for by its caller or
    # escaped at the boundary, and anything added since came from a permitted plugin.
    # Saying so in the type is what tells a shortcode author not to escape it — and makes
    # escaping it anyway a harmless no-op rather than a bug that shows the markup to the
    # reader as literal text.
    return shortcode.render(attrs, Markup(inner))


def _close_unclosed_above(
    stack: list[_Frame], depth: int, shortcodes: dict[str, Shortcode]
) -> None:
    """Discharge frames left open above ``depth``, treating each as a void tag.

    An opening tag that is never closed renders with empty content, and the text that
    followed it stays outside — the same shape ``[image url="…"]`` relies on, so a tag
    that takes no closing tag and one whose author forgot it are handled alike. Telling
    them apart needs shortcodes to declare a kind, which they do not yet.

    Args:
        stack: The parse stack, mutated in place.
        depth: Index of the frame to stop at; everything above it is discharged.
        shortcodes: Registered shortcodes, keyed by tag name.
    """
    while len(stack) - 1 > depth:
        name, raw_attrs, parts = stack.pop()
        stack[-1][2].append(_render_tag(shortcodes[name], raw_attrs, ""))
        stack[-1][2].extend(parts)


def _open_frame_for(stack: list[_Frame], name: str) -> int | None:
    """Find the innermost frame a closing tag could belong to.

    Args:
        stack: The parse stack.
        name: The tag name being closed.

    Returns:
        Index of the matching frame, or None if nothing on the stack opened this tag.
    """
    for index in range(len(stack) - 1, 0, -1):
        if stack[index][0] == name:
            return index
    return None


def _apply_shortcodes(content: str, shortcodes: dict[str, Shortcode]) -> str:
    """Render every registered shortcode in the content, innermost tag first.

    Tokenises once and matches tags with a stack, so a tag nests inside another of the
    same name and a closing tag pairs with the opening tag it actually belongs to. A
    closing tag with nothing to close, and any tag name not registered here, are left in
    the content as the author wrote them.

    Args:
        content: Content to scan for shortcode tags.
        shortcodes: Registered shortcodes, keyed by tag name.

    Returns:
        The content with every registered shortcode replaced by its rendered HTML.
    """
    if not shortcodes:
        return content

    stack: list[_Frame] = [("", "", [])]
    position = 0

    for match in _tag_pattern(shortcodes).finditer(content):
        stack[-1][2].append(content[position : match.start()])
        position = match.end()
        closing, opening, raw_attrs = match.group(1), match.group(2), match.group(3)

        if closing is None:
            stack.append((opening, raw_attrs or "", []))
            continue

        depth = _open_frame_for(stack, closing)
        if depth is None:
            stack[-1][2].append(match.group(0))
            continue

        _close_unclosed_above(stack, depth, shortcodes)
        name, attrs_text, parts = stack.pop()
        stack[-1][2].append(_render_tag(shortcodes[name], attrs_text, "".join(parts)))

    stack[-1][2].append(content[position:])
    _close_unclosed_above(stack, 0, shortcodes)
    return "".join(stack[0][2])


class ContentTransformerPluginBase(PluginBase, ABC):
    """Base class for content-transformer plugins.

    Subclasses declare which content types they want to transform via
    ``accepted_content_types``. That declaration is the set of choices an operator is
    offered, not a grant: they still name each type in ``allowed_content_types``, and
    silence is refusal.

    A plugin with no technical constraint on where it runs declares
    ``ALL_CONTENT_TYPES`` — offering every type in the vocabulary, including ones invented
    after it was written. A plugin that does have a constraint enumerates: one whose
    shortcode embeds raw markup, reaches an external host, or costs something to run
    cannot honestly claim to work anywhere, and naming its types is how it says so.

    Enumerating is *not* how a plugin keeps itself out of comments — whether commenters
    may use it is the operator's policy, and their grant already decides it. A plugin may
    also name a kind of content some other package brings — accepting one never means
    importing that package — and still install on an
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

    accepted_content_types: Mapping[ContentType, str] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Reject a declaration that asks for a content type without saying why.

        Required, not encouraged: the rationale is shown beside the checkbox an operator
        ticks, and a reason nothing enforces is a reason that rots.

        Raises:
            ValueError: If a declared content type carries no rationale.
        """
        super().__init_subclass__(**kwargs)
        declared = cls.__dict__.get("accepted_content_types")
        if declared is None:
            return
        if not isinstance(declared, Mapping):
            raise ValueError(
                f"{cls.__name__}.accepted_content_types must map each content type to the "
                f"reason this plugin needs it; got {type(declared).__name__}."
            )
        # Typed as Mapping[ContentType, str], but an untyped plugin can put anything here.
        for content_type, reason in cast("Mapping[object, object]", declared).items():
            if not isinstance(reason, str) or not reason.strip():
                name = "ALL_CONTENT_TYPES" if content_type is ALL_CONTENT_TYPES else content_type
                raise ValueError(
                    f"{cls.__name__}.accepted_content_types[{name!r}] needs a reason an "
                    f"operator can read when deciding whether to grant it."
                )

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


def _plugin_label(plugin: "ContentTransformerPluginBase") -> str:
    """Name a plugin the way an operator would recognise it in a log.

    Args:
        plugin: The plugin to name.

    Returns:
        The plugin's config key, or its class name if it was never registered with an
        engine and so has no key stamped on it yet.
    """
    return plugin.name or type(plugin).__name__


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

        ``ALL_CONTENT_TYPES`` turns the first key for anything in the vocabulary, and
        nothing more — the operator still names each type they want acted on.

        Args:
            plugin: The content-transformer plugin to check.
            content_type: The kind of content it wants to act on.

        Returns:
            True if the plugin is both willing and permitted.
        """
        if content_type not in self.acceptable_content_types(plugin):
            return False
        return content_type in self._allowlist.get(plugin, frozenset())

    def acceptable_content_types(self, plugin: ContentTransformerPluginBase) -> set[ContentType]:
        """The content types an operator may grant this plugin — its declaration, resolved.

        The set of choices, not the decision: an admin panel offers exactly these and the
        operator ticks the ones they want, which become ``allowed_content_types``. A
        wildcard offers everything in the vocabulary; an enumeration offers only what it
        names.

        Resolved on each call rather than cached, because plugins contribute content types
        as they load and the vocabulary is only complete once loading is done.

        Args:
            plugin: The plugin whose declaration to resolve.

        Returns:
            The content types this plugin may be granted.
        """
        if _wildcard_reason(plugin.accepted_content_types) is not None:
            return set(self.known_content_types)
        return set(plugin.accepted_content_types)

    def rationale_for(self, plugin: ContentTransformerPluginBase, content_type: ContentType) -> str:
        """Why this plugin is asking for this content type, in its author's words.

        Shown beside the checkbox an operator ticks. A plugin that enumerates gives a
        reason per type; one declaring ``ALL_CONTENT_TYPES`` gives a single reason that
        stands for every type it is offered.

        Args:
            plugin: The plugin whose declaration to read.
            content_type: The content type being offered.

        Returns:
            The rationale, or an empty string if this plugin is not offered that type.
        """
        declared = plugin.accepted_content_types
        wildcard = _wildcard_reason(declared)
        if wildcard is not None:
            return wildcard if content_type in self.known_content_types else ""
        return declared.get(content_type, "")

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
            permitted plugin is taken from the *first*, which is the same one prose gets:
            transformers run in order and the first to own a tag consumes it, so a later
            registration could never have rendered it anyway. Taking the last here would
            make a stored value render differently from the identical tag in a post body.
        """
        permitted: dict[str, Shortcode] = {}
        owners: dict[str, str] = {}
        for plugin in plugins:
            if not self.may_transform(plugin, content_type):
                continue
            for tag_name, shortcode in plugin.shortcodes.items():
                if tag_name in permitted:
                    logger.warning(
                        "Plugin %r registers shortcode %r, already registered by %r for "
                        "content type '%s'. The earlier plugin wins; reorder the plugins "
                        "in the config to change which.",
                        _plugin_label(plugin),
                        tag_name,
                        owners[tag_name],
                        content_type,
                    )
                    continue
                permitted[tag_name] = shortcode
                owners[tag_name] = _plugin_label(plugin)
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
