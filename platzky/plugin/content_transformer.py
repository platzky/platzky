"""ContentTransformerPluginBase capability — plugins that transform content."""

from __future__ import annotations

import logging
import re
from abc import ABC
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from itertools import zip_longest
from typing import ClassVar, cast

import jinja2.ext
from markupsafe import Markup, escape

from platzky.content_types import ALL_CONTENT_TYPES, ContentType
from platzky.plugin.plugin import PluginBase
from platzky.plugin.plugin_config import PluginConfigBase
from platzky.shortcodes import Shortcode, ShortcodeAttrs, ShortcodeError


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


#: HTML tags, held back from text filters. Only the HTML half of what this used to match:
#: shortcode syntax no longer needs protecting here, because parsing has already lifted it
#: out of the text by the time a filter runs.
_HTML_TAG_RE = re.compile(r"<[^>]*>")

_MAX_ATTR_NAME_LEN = 100
_MAX_ATTR_VALUE_LEN = 2048
_ATTR_RE = re.compile(rf'([\w-]{{1,{_MAX_ATTR_NAME_LEN}}})="([^"]{{0,{_MAX_ATTR_VALUE_LEN}}})"')


@dataclass
class _Text:
    """Author text between tags — the only thing a text filter is allowed to touch."""

    text: str


@dataclass
class _Verbatim:
    """A raw shortcode's body: parsed by nobody, filtered by nobody."""

    shortcode: Shortcode
    raw_attrs: str
    body: str


@dataclass
class _Element:
    """A shortcode tag and everything written inside it."""

    shortcode: Shortcode
    raw_attrs: str
    children: list["_Node"]


_Node = _Text | _Verbatim | _Element

#: One frame of the parse stack: tag name, its raw attribute text, the nodes collected
#: inside it so far, and where the opening tag was written — kept so an unclosed tag can
#: say which one it was. The outermost frame is the document itself and carries ``""`` as
#: its name, which no shortcode can have.
_Frame = tuple[str, str, list[_Node], int]


def _tag_pattern(shortcodes: dict[str, Shortcode]) -> re.Pattern[str]:
    """Build the token pattern matching an opening or closing tag of a known shortcode.

    Args:
        shortcodes: Registered shortcodes, keyed by tag name.

    Returns:
        A pattern whose groups are (closing name, opening name, opening attributes).
    """
    names = "|".join(re.escape(n) for n in shortcodes)
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


class _MarkupStripper(HTMLParser):
    """Collect the text of a document, discarding its tags.

    A real parser rather than a regex over ``<[^>]*>``, because ``>`` is legal inside a
    quoted attribute: ``<img alt="a > b" src="/a.png">`` ends at the first ``>`` as far as
    a regex is concerned, which would leave the rest of the tag behind as visible text.
    """

    def __init__(self) -> None:
        """Start with no text collected and nothing removed."""
        super().__init__(convert_charrefs=False)
        self.text: list[str] = []
        self.removed: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:  # noqa: ARG002
        """Drop an opening tag, recording that it was there."""
        self.removed.append(tag)

    def handle_startendtag(self, tag: str, attrs: object) -> None:  # noqa: ARG002
        """Drop a self-closing tag, recording that it was there."""
        self.removed.append(tag)

    def handle_endtag(self, tag: str) -> None:
        """Drop a closing tag without recording it; its opener already counted."""

    def handle_comment(self, data: str) -> None:  # noqa: ARG002
        """Drop a comment, recording it under a name an operator will recognise."""
        self.removed.append("<!--")

    def handle_data(self, data: str) -> None:
        """Keep ordinary text, which includes any shortcode tags written in it."""
        self.text.append(data)

    def handle_entityref(self, name: str) -> None:
        """Keep a named entity as written, rather than resolving it."""
        self.text.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        """Keep a numeric entity as written, rather than resolving it."""
        self.text.append(f"&#{name};")


def _strip_markup(text: str) -> tuple[str, list[str]]:
    """Remove HTML tags from content, keeping the text they wrapped.

    Shortcode syntax is untouched: brackets are ordinary characters to an HTML parser, so
    ``[image url="/a.png"]`` survives to be rendered by the pipeline afterwards.

    Args:
        text: Content to strip.

    Returns:
        The text without its tags, and the names of the tags removed, in document order.
    """
    stripper = _MarkupStripper()
    stripper.feed(text)
    stripper.close()
    return "".join(stripper.text), stripper.removed


def _never_closed(name: str) -> str:
    """Phrase the complaint about an opening tag that is never closed.

    Args:
        name: The tag name.

    Returns:
        A message naming the closing tag the author owes.
    """
    return f"[{name}] is never closed; add [/{name}]"


def _closes_nothing(shortcode: Shortcode) -> str:
    """Phrase the complaint about a closing tag that matches no opening one.

    A void shortcode gets its own wording, since the author's mistake there is not a
    missing opening tag but the belief that this tag takes a closing one at all.

    Args:
        shortcode: The shortcode the closing tag named.

    Returns:
        A message describing what is wrong.
    """
    if shortcode.kind == "void":
        return f"[/{shortcode.name}] is not valid; [{shortcode.name}] takes no closing tag"
    return f"[/{shortcode.name}] closes nothing; no [{shortcode.name}] is open here"


def _reject_unclosed_above(
    stack: list[_Frame], depth: int, shortcodes: dict[str, Shortcode], *, strict: bool
) -> None:
    """Discharge any block tag still open above ``depth``.

    Only block tags ever reach the stack — void and raw ones are rendered on sight — so
    anything left open here was written with no closing tag by an author who owed one.
    Rendering it anyway would silently drop or reparent whatever it was meant to wrap, so
    under ``strict`` the parse fails and names the tag. Otherwise the tag renders empty
    and its contents are kept, which is what platzky did before it could tell a void tag
    from an unclosed one.

    Args:
        stack: The parse stack, mutated in place.
        depth: Index of the frame to stop at; everything above it must be closed by now.
        shortcodes: Registered shortcodes, keyed by tag name.
        strict: Whether an unclosed tag is an error rather than something to render past.

    Raises:
        ShortcodeError: If ``strict`` and a block tag above ``depth`` was never closed.
    """
    if strict and len(stack) - 1 > depth:
        name, _, _, position = stack[-1]
        raise ShortcodeError(_never_closed(name), name, position)
    while len(stack) - 1 > depth:
        name, raw_attrs, children, _ = stack.pop()
        stack[-1][2].append(_Element(shortcodes[name], raw_attrs, []))
        stack[-1][2].extend(children)


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


def _parse(content: str, shortcodes: dict[str, Shortcode], *, strict: bool) -> list[_Node]:
    """Read the content into nodes, without rendering anything.

    Tokenises once and matches tags with a stack, so a tag nests inside another of the
    same name and a closing tag pairs with the opening tag it actually belongs to. A
    ``"raw"`` tag is not descended into: its body is taken verbatim up to the matching
    closing tag, so brackets inside it are characters rather than syntax.

    A tag name no plugin registered is left exactly as written — an author may be writing
    *about* a shortcode rather than using one, and platzky has no opinion on a name it
    does not know. A registered name used wrongly is a different matter and is reported
    when ``strict``: there is no rendering of an unclosed tag, or of a closing tag that
    closes nothing, that is not a guess about what the author meant.

    Args:
        content: Content to scan for shortcode tags.
        shortcodes: Registered shortcodes, keyed by tag name.
        strict: Whether a malformed tag is an error. True for content someone vouched
            for, since whoever wrote it has write access and can fix the bracket. False
            otherwise, because a stranger's typo must not take a page down — and because
            escaping mangles a tag on the way in, so unvouched content arrives malformed
            through no fault of its author: quotes become entities, the opening tag stops
            matching, and its closing tag is left with nothing to close.

    Returns:
        The document as a list of nodes.

    Raises:
        ShortcodeError: If ``strict`` and a tag is opened and never closed, or a closing
            tag matches no opening one.
    """
    pattern = _tag_pattern(shortcodes)
    stack: list[_Frame] = [("", "", [], 0)]
    position = 0

    while (match := pattern.search(content, position)) is not None:
        if match.start() > position:
            stack[-1][2].append(_Text(content[position : match.start()]))
        position = match.end()
        closing, opening, raw_attrs = match.group(1), match.group(2), match.group(3)

        if closing is not None:
            depth = _open_frame_for(stack, closing)
            if depth is None:
                if strict:
                    raise ShortcodeError(
                        _closes_nothing(shortcodes[closing]), closing, match.start()
                    )
                stack[-1][2].append(_Text(match.group(0)))
                continue
            _reject_unclosed_above(stack, depth, shortcodes, strict=strict)
            name, attrs_text, children, _ = stack.pop()
            stack[-1][2].append(_Element(shortcodes[name], attrs_text, children))
            continue

        shortcode = shortcodes[opening]
        if shortcode.kind == "void":
            stack[-1][2].append(_Element(shortcode, raw_attrs or "", []))
        elif shortcode.kind == "raw":
            body_end = content.find(f"[/{opening}]", position)
            if body_end < 0:
                if strict:
                    raise ShortcodeError(_never_closed(opening), opening, match.start())
                stack[-1][2].append(_Text(match.group(0)))
                continue
            stack[-1][2].append(_Verbatim(shortcode, raw_attrs or "", content[position:body_end]))
            position = body_end + len(opening) + 3
        else:
            stack.append((opening, raw_attrs or "", [], match.start()))

    if position < len(content):
        stack[-1][2].append(_Text(content[position:]))
    _reject_unclosed_above(stack, 0, shortcodes, strict=strict)
    return stack[0][2]


def _strip_text_nodes(nodes: list[_Node]) -> list[str]:
    """Remove HTML tags from the document's author text, keeping the text they wrapped.

    Runs over the parsed document rather than the source string, which is what lets it
    leave a ``"raw"`` body alone. A raw body is verbatim by declaration — no filter reaches
    it and no shortcode inside it renders — and that holds for this pass too, so the tag is
    also how an author says "this HTML is meant" on a site that strips the rest. The escape
    hatch is only open to whoever vouched for the content: unvouched content was escaped at
    the boundary, raw bodies with it, so nothing there can pass a tag through.

    Args:
        nodes: The parsed document, modified in place.

    Returns:
        The names of the tags removed, in document order.
    """
    removed: list[str] = []
    for node in nodes:
        if isinstance(node, _Text):
            node.text, gone = _strip_markup(node.text)
            removed.extend(gone)
        elif isinstance(node, _Element):
            removed.extend(_strip_text_nodes(node.children))
    return removed


def _filter_text(nodes: list[_Node], filters: Sequence[Callable[[str], str]]) -> None:
    """Run every text filter over the document's text, and nothing else.

    This is what separating parsing from rendering buys. A filter now sees only what an
    author typed between tags: never a tag's attributes, never another shortcode's output,
    and never the body of a ``"raw"`` tag. Previously each plugin rendered its own
    shortcodes before handing a flat string to the next, so a later plugin's filter was
    handed markup earlier ones had produced and could corrupt it.

    HTML the author wrote is still held back from filters by ``_HTML_TAG_RE`` — the one
    kind of markup that is still text at this point, since platzky parses shortcodes but
    not HTML. Filters are re-applied one at a time so a filter's own output is held back
    from the next one too.

    Args:
        nodes: The parsed document, modified in place.
        filters: Each permitted plugin's ``transform_text``, in pipeline order.
    """
    for node in nodes:
        if isinstance(node, _Text):
            node.text = _filter_around_html(node.text, filters)
        elif isinstance(node, _Element):
            _filter_text(node.children, filters)


def _filter_around_html(text: str, filters: Sequence[Callable[[str], str]]) -> str:
    """Apply each filter to the text, keeping HTML tags out of their reach.

    Args:
        text: A single run of author text.
        filters: Filters to apply, in order.

    Returns:
        The text after every filter has run over its non-tag parts.
    """
    for transform in filters:
        parts = _HTML_TAG_RE.split(text)
        tags = _HTML_TAG_RE.findall(text)
        text = "".join(
            segment
            for pair in zip_longest([transform(p) for p in parts], tags, fillvalue="")
            for segment in pair
        )
    return text


def _render(nodes: Sequence[_Node]) -> str:
    """Render a parsed document to HTML, innermost tag first.

    Args:
        nodes: The parsed, filtered document.

    Returns:
        The rendered HTML.
    """
    rendered: list[str] = []
    for node in nodes:
        if isinstance(node, _Text):
            rendered.append(node.text)
        elif isinstance(node, _Verbatim):
            rendered.append(_render_tag(node.shortcode, node.raw_attrs, node.body))
        else:
            rendered.append(_render_tag(node.shortcode, node.raw_attrs, _render(node.children)))
    return "".join(rendered)


def _render_document(
    content: str,
    shortcodes: dict[str, Shortcode],
    filters: Sequence[Callable[[str], str]],
    *,
    strict: bool,
    strip_html: bool = False,
) -> tuple[str, list[str]]:
    """Parse the content once, strip and filter its text, then render its tags.

    The order is the point. Rendering used to happen inside the per-plugin loop, so every
    stage flattened the document back to a string and the next one had to rediscover it —
    which is how a filter came to be handed markup an earlier shortcode had produced.
    Stripping joined the same pass for the same reason: run over the source string before
    parsing, it could not tell HTML an author left in prose from HTML they marked to keep.

    Args:
        content: The content to transform.
        shortcodes: Every shortcode permitted here, keyed by tag name.
        filters: Every permitted ``transform_text``, in pipeline order.
        strict: Whether a malformed tag is an error.
        strip_html: Whether to remove HTML tags the author wrote. Applies to author text
            only: a raw body is verbatim, so what is written there survives.

    Returns:
        The rendered content, and the names of the HTML tags stripped from it.

    Raises:
        ShortcodeError: If ``strict`` and a shortcode tag is malformed.
    """
    nodes: list[_Node] = (
        _parse(content, shortcodes, strict=strict) if shortcodes else [_Text(content)]
    )
    removed = _strip_text_nodes(nodes) if strip_html else []
    _filter_text(nodes, filters)
    return _render(nodes), removed


class ContentTransformerPluginBase(PluginBase, ABC):
    """Base class for content-transformer plugins.

    Subclasses declare which content types they want to transform via
    ``accepted_content_types``. That declaration is the set of choices an operator is
    offered, not a grant: they still name each type in ``allowed_content_types``, and
    silence is refusal.

    A plugin with no technical constraint on where it runs declares
    ``ALL_CONTENT_TYPES`` — offering every type in the vocabulary, including ones invented
    after it was written. A plugin that does have a constraint names each type it can
    serve: one whose shortcode emits block-level layout markup, reaches an external host,
    or costs something to run cannot honestly claim to work anywhere, and naming its types
    is how it says so.

    Naming types is *not* how a plugin keeps itself out of comments — whether commenters
    may use it is the operator's policy, and their grant already decides it. A plugin may
    also name a kind of content some other package brings — accepting one never means
    importing that package — and still install on an
    application that has no such content, where it is simply never called. To *bring* a
    content type, see ``PluginBase.provides_content_types``. The engine enforces final
    routing — ``Engine.may_transform`` decides, not the plugin, so widening
    ``accepted_content_types`` cannot widen the operator's grant.

    Declare ``shortcodes`` to register shortcode tags; they are applied automatically by
    ``Engine.transform_content``, which is the only thing that runs a plugin — a plugin
    never transforms content itself, because running one is the registry's job and the
    gate is where it makes its decision. An application rendering a *stored value*
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
        wildcard offers everything in the vocabulary; a declaration that names types offers
        only those.

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

        Shown beside the checkbox an operator ticks. A plugin that names its types gives a
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
        *,
        strip_html: bool = False,
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
            strip_html: Overrule vouching and remove HTML tags the author wrote, keeping
                the text they wrapped and logging what went. The operator's call, behind
                ``STRIP_CONTENT_HTML``: shortcodes still render, but a site turning it on
                needs some other way to format a post, because HTML is currently the only
                one platzky has. A ``"raw"`` shortcode body is exempt: it is verbatim by
                declaration, which makes it the way an author marks HTML they mean to
                keep. Only vouched content has one — unvouched content is escaped at the
                boundary, raw bodies included.

        Returns:
            The content after every permitted transformer has run.
        """
        # Whether anyone vouched decides three separate things, so read it before escaping
        # flattens the Markup away: what gets escaped, whose mistakes get reported, and
        # whether there is any authored HTML left for the operator to strip.
        vouched = hasattr(content, "__html__")
        # escape() is a no-op on anything carrying __html__, so this is the whole rule.
        # It makes content safe; it does not stop shortcode parsing. Brackets survive, so
        # a bare tag in untrusted content still fires — harmlessly, since what it wraps is
        # already escaped — while a quoted attribute does not survive and that tag renders
        # literally. Safety does not depend on which happens.
        content = str(escape(content))
        # That mangling is also why only vouched content is parsed strictly. Escaping the
        # quotes out of `[tag a="b"]x[/tag]` leaves an opening tag that no longer matches
        # and a closing tag that does, so a stranger writing an ordinary shortcode would
        # otherwise fail the render — a typo in a comment must not take a page down.
        permitted = [p for p in plugins if self.may_transform(p, content_type)]
        # One parse for the whole pipeline, then any stripping, then every filter, then
        # every shortcode. The plugins are no longer run one after another over a flat
        # string: doing that made each stage re-derive the document the previous one had
        # just discarded, and handed every filter the markup earlier shortcodes had
        # produced.
        rendered, removed = _render_document(
            content,
            self.shortcodes_for(permitted, content_type),
            [plugin.transform_text for plugin in permitted],
            strict=vouched,
            # Unvouched content was escaped above, raw bodies with it, so it has no tags
            # left to strip and no way to pass one through a raw body either.
            strip_html=strip_html and vouched,
        )
        if removed:
            # Lossy and silent otherwise, so say what went and how much of it.
            logger.warning(
                "Removed %d HTML tag(s) from %s content (%s) because STRIP_CONTENT_HTML "
                "is on. The text they wrapped was kept.",
                len(removed),
                content_type,
                ", ".join(sorted(set(removed))),
            )
        return rendered

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
