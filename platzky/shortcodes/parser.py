"""Shortcode parsing and rendering — the document machinery behind ``transform_content``.

Plugins register handlers through the ``shortcodes`` class variable on
``ContentTransformerPluginBase``. A shortcode declares its ``kind``, which is what says
whether a closing tag belongs::

    [tagname attr="val"]                     # kind = "void"
    [tagname attr="val"]content[/tagname]    # kind = "block"  (the default)

Shortcodes nest, including inside another of the same name: tags are matched with a
stack, so a closing tag pairs with the opening tag it belongs to rather than the nearest
one.

Malformed content is reported rather than guessed at. A ``"block"`` tag that is never
closed raises ``ShortcodeError`` naming the tag and where it was written, because there
is no rendering of it that is not a guess about what the author meant to wrap. What is
*not* malformed passes through untouched: a closing tag with nothing to close, and any
tag name no plugin registered, are left exactly as written — an author may be writing
about a shortcode rather than using one.

A document is parsed once and then walked three times — strip, filter, render — so that
no pass ever sees what a later one produces. ``render_document`` is the whole of the
public surface; everything else here serves it.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser

from markupsafe import Markup

from platzky.shortcodes.shortcode import Shortcode, ShortcodeAttrs, ShortcodeError

logger = logging.getLogger(__name__)


#: HTML tags, held back from text filters. Only the HTML half of what this used to match:
#: shortcode syntax no longer needs protecting here, because parsing has already lifted it
#: out of the text by the time a filter runs.
#: Captured, so ``split`` returns the tags along with the text between them: the odd
#: indices of the result are the tags.
_HTML_TAG_RE = re.compile(r"(<[^>]*>)")

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
        """Drop a comment, recording it under a name a site owner will recognise."""
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


def _text_nodes(nodes: Sequence[_Node]) -> Iterator[_Text]:
    """Yield every author-text node in the document, outermost first.

    The one definition of what the text passes reach. ``_Verbatim`` is skipped and never
    descended into, which is what makes a ``"raw"`` body verbatim against filters and
    against ``STRIP_CONTENT_HTML`` alike — one rule, stated once, rather than each pass
    remembering it.

    Args:
        nodes: The parsed document.

    Yields:
        Each ``_Text`` node, including those nested inside shortcode elements.
    """
    for node in nodes:
        if isinstance(node, _Text):
            yield node
        elif isinstance(node, _Element):
            yield from _text_nodes(node.children)


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
    for node in _text_nodes(nodes):
        node.text, gone = _strip_markup(node.text)
        removed.extend(gone)
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
    for node in _text_nodes(nodes):
        node.text = _filter_around_html(node.text, filters)


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
        text = "".join(part if index % 2 else transform(part) for index, part in enumerate(parts))
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


def render_document(
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
