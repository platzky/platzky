"""Shortcode parsing and rendering — the document machinery behind ``transform_content``.

A document is parsed once into nodes, then walked three times — strip, filter, render —
so no pass ever sees what a later one produces. ``render_document`` is the whole public
surface; everything else here serves it.

Shortcodes nest, including inside another of the same name: tags are matched with a stack,
so a closing tag pairs with the opening tag it belongs to rather than the nearest one.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser

from markupsafe import Markup

from platzky.shortcodes.shortcode import ElementRefused, Shortcode, ShortcodeError

logger = logging.getLogger(__name__)


#: HTML tags, held back from text filters. Captured, so ``split`` returns the tags along
#: with the text between them: the odd indices of the result are the tags.
#:
#: Quote-aware, because ``>`` is legal inside an attribute: ``<[^>]*>`` ends
#: ``<a title="a > b">`` at the first ``>`` and hands ``` b">`` to every filter, which the
#: filter contract says never happens. Same hazard ``_MarkupStripper`` exists to avoid.
_HTML_TAG_RE = re.compile(r"""(<(?:[^>"']|"[^"]*"|'[^']*')*>)""")

_MAX_ATTR_NAME_LEN = 100
_MAX_ATTR_VALUE_LEN = 2048
_ATTR_RE = re.compile(rf'([\w-]{{1,{_MAX_ATTR_NAME_LEN}}})="([^"]{{0,{_MAX_ATTR_VALUE_LEN}}})"')


@dataclass
class _Text:
    """Text outside any shortcode element, including HTML and unregistered brackets.

    The only node a filter may touch and the only one ``STRIP_CONTENT_HTML`` reaches.
    """

    text: str


@dataclass
class _RawElement:
    """A ``"raw"`` element: its content is the characters between the tags, unparsed.

    A string rather than nodes because the parser never descended into it — which is what
    keeps it verbatim against filters and against ``STRIP_CONTENT_HTML``.
    """

    shortcode: Shortcode
    raw_attrs: str
    content: str


@dataclass
class _Element:
    """A shortcode element whose content was parsed into nodes.

    Every kind but ``"raw"`` ends up here; a ``"void"`` shortcode simply has no children.
    """

    shortcode: Shortcode
    raw_attrs: str
    children: list["_Node"]


_Node = _Text | _RawElement | _Element


@dataclass
class _Frame:
    """An element the parser has opened and not yet closed.

    The bottom frame is the document itself, so appending to ``stack[-1]`` needs no special
    case for top level; its name is ``""``, which no shortcode can have.
    """

    name: str
    raw_attrs: str
    children: list["_Node"]

    #: Where the opening tag was written, carried only so an unclosed element can say which
    #: one it was.
    position: int


def _tag_pattern(shortcodes: dict[str, Shortcode]) -> re.Pattern[str]:
    """Match an opening or closing tag of a known shortcode, grouped (close, open, attrs)."""
    names = "|".join(re.escape(n) for n in shortcodes)
    return re.compile(rf"\[/({names})\]|\[({names})((?:\s+[\w-]+=\"[^\"]*\")*)\s*\]")


def _render_element(
    shortcode: Shortcode, raw_attrs: str, content: str, children: Sequence[Markup]
) -> str:
    """Render one element with its parsed attributes and already-rendered content.

    Args:
        shortcode: The shortcode to render.
        raw_attrs: The attribute text as written in the opening tag.
        content: What the element wraps, with nested elements already rendered.
        children: The same, kept as one entry per element child — what a wrapper counts
            rather than scanning ``content`` for markup its children happened to produce.

    Returns:
        The shortcode's replacement HTML, or nothing at all when it refused itself.
    """
    try:
        attrs = shortcode.attributes.bind(dict(_ATTR_RE.findall(raw_attrs)))
        # Markup truthfully: the content was either vouched for by its caller or escaped at
        # the boundary, and anything added since came from a permitted plugin. The type is
        # what tells a shortcode author not to escape it again.
        return shortcode.render(attrs, Markup(content), children)
    except ElementRefused as refusal:
        # One element, not the page: an author's typo costs its own tag. Logged because an
        # author cannot see an absence, and named by tag so they can find which one.
        logger.warning("[%s] rendered nothing: %s.", shortcode.name, refusal)
        return ""


class _MarkupStripper(HTMLParser):
    """Collect the text of a document, discarding its tags.

    A parser rather than a regex over ``<[^>]*>``, because ``>`` is legal inside a quoted
    attribute: ``<img alt="a > b" src="/a.png">`` would leave half a tag behind as text.
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
    """Remove HTML tags, keeping the text they wrapped.

    Shortcode syntax survives: brackets are ordinary characters to an HTML parser.

    Args:
        text: Content to strip.

    Returns:
        The text without its tags, and the tag names removed, in document order.
    """
    stripper = _MarkupStripper()
    stripper.feed(text)
    stripper.close()
    return "".join(stripper.text), stripper.removed


def _never_closed(name: str) -> str:
    """Phrase the complaint about an opening tag that is never closed."""
    return f"[{name}] is never closed; add [/{name}]"


def _closes_nothing(shortcode: Shortcode) -> str:
    """Phrase the complaint about a closing tag that matches no opening one.

    A void shortcode gets its own wording: the mistake there is not a missing opening tag
    but the belief that this shortcode takes a closing one at all.
    """
    if shortcode.kind == "void":
        return f"[/{shortcode.name}] is not valid; [{shortcode.name}] takes no closing tag"
    return f"[/{shortcode.name}] closes nothing; no [{shortcode.name}] is open here"


def _discharge_unclosed_above(
    stack: list[_Frame], depth: int, shortcodes: dict[str, Shortcode], *, strict: bool
) -> None:
    """Discharge any element still open above ``depth``.

    Rendering an unclosed element would silently drop or reparent what it was meant to
    wrap, so under ``strict`` the parse fails and names it; otherwise it renders empty and
    its contents are kept.

    Args:
        stack: The parse stack, mutated in place.
        depth: Index of the frame to stop at; everything above it must be closed by now.
        shortcodes: Registered shortcodes, keyed by tag name.
        strict: Whether an unclosed element is an error rather than something to render past.

    Raises:
        ShortcodeError: If ``strict`` and an element above ``depth`` was never closed.
    """
    if strict and len(stack) - 1 > depth:
        unclosed = stack[-1]
        raise ShortcodeError(_never_closed(unclosed.name), unclosed.name, unclosed.position)
    while len(stack) - 1 > depth:
        frame = stack.pop()
        stack[-1].children.append(_Element(shortcodes[frame.name], frame.raw_attrs, []))
        stack[-1].children.extend(frame.children)


def _open_frame_for(stack: list[_Frame], name: str) -> int | None:
    """Index of the innermost frame this closing tag could belong to, or None."""
    for index in range(len(stack) - 1, 0, -1):
        if stack[index].name == name:
            return index
    return None


def _close_element(
    stack: list[_Frame],
    match: re.Match[str],
    name: str,
    shortcodes: dict[str, Shortcode],
    *,
    strict: bool,
) -> None:
    """Close the element this tag belongs to, or keep the tag as text.

    Args:
        stack: The parse stack, mutated in place.
        match: The closing tag's match, for its position and raw text.
        name: The tag name being closed.
        shortcodes: Registered shortcodes, keyed by tag name.
        strict: Whether a tag that closes nothing is an error.

    Raises:
        ShortcodeError: If ``strict`` and this closing tag closes nothing.
    """
    depth = _open_frame_for(stack, name)
    if depth is None:
        if strict:
            raise ShortcodeError(_closes_nothing(shortcodes[name]), name, match.start())
        stack[-1].children.append(_Text(match.group(0)))
        return
    _discharge_unclosed_above(stack, depth, shortcodes, strict=strict)
    frame = stack.pop()
    stack[-1].children.append(_Element(shortcodes[frame.name], frame.raw_attrs, frame.children))


def _open_element(
    stack: list[_Frame],
    content: str,
    match: re.Match[str],
    name: str,
    shortcodes: dict[str, Shortcode],
    *,
    strict: bool,
) -> int:
    """Take an opening tag: render it on sight, take its raw content, or push a frame.

    Args:
        stack: The parse stack, mutated in place.
        content: The whole document, for a raw element's content.
        match: The opening tag's match, for its position and raw text.
        name: The tag name being opened.
        shortcodes: Registered shortcodes, keyed by tag name.
        strict: Whether a raw element that is never closed is an error.

    Returns:
        Where scanning continues — past a raw element's closing tag, otherwise just past
        the opening tag.

    Raises:
        ShortcodeError: If ``strict`` and a raw element is never closed.
    """
    shortcode = shortcodes[name]
    raw_attrs = match.group(3) or ""
    after_tag = match.end()
    if shortcode.kind == "void":
        stack[-1].children.append(_Element(shortcode, raw_attrs, []))
        return after_tag
    if shortcode.kind == "raw":
        end = content.find(f"[/{name}]", after_tag)
        if end < 0:
            if strict:
                raise ShortcodeError(_never_closed(name), name, match.start())
            stack[-1].children.append(_Text(match.group(0)))
            return after_tag
        stack[-1].children.append(_RawElement(shortcode, raw_attrs, content[after_tag:end]))
        return end + len(name) + 3
    stack.append(_Frame(name, raw_attrs, [], match.start()))
    return after_tag


def _parse(content: str, shortcodes: dict[str, Shortcode], *, strict: bool) -> list[_Node]:
    """Read the content into nodes, rendering nothing.

    A tag name no plugin registered is left exactly as written — an author may be writing
    *about* a shortcode rather than using one. A registered name used wrongly is reported
    when ``strict``.

    Args:
        content: Content to scan for shortcode tags.
        shortcodes: Registered shortcodes, keyed by tag name.
        strict: Whether a malformed tag is an error. True for content someone vouched for,
            whose writer can fix the bracket. False otherwise: a stranger's typo must not
            take a page down, and escaping mangles their tags on the way in — quotes become
            entities, so the opening tag stops matching while its closing tag still does.

    Returns:
        The document as a list of nodes.

    Raises:
        ShortcodeError: If ``strict`` and a tag is never closed, or closes nothing.
    """
    pattern = _tag_pattern(shortcodes)
    stack: list[_Frame] = [_Frame("", "", [], 0)]
    position = 0

    while (match := pattern.search(content, position)) is not None:
        if match.start() > position:
            stack[-1].children.append(_Text(content[position : match.start()]))
        position = match.end()
        closing, opening = match.group(1), match.group(2)
        if closing is not None:
            _close_element(stack, match, closing, shortcodes, strict=strict)
        else:
            position = _open_element(stack, content, match, opening, shortcodes, strict=strict)

    if position < len(content):
        stack[-1].children.append(_Text(content[position:]))
    _discharge_unclosed_above(stack, 0, shortcodes, strict=strict)
    return stack[0].children


def _text_nodes(nodes: Sequence[_Node]) -> Iterator[_Text]:
    """Yield every text node, never descending into a ``_RawElement``.

    The one definition of what the text passes reach, so "raw content is verbatim" is a
    property of the walk rather than a rule each pass has to remember.
    """
    for node in nodes:
        if isinstance(node, _Text):
            yield node
        elif isinstance(node, _Element):
            yield from _text_nodes(node.children)


def _strip_text_nodes(nodes: list[_Node]) -> list[str]:
    """Remove HTML from the document's text, returning the tag names removed."""
    removed: list[str] = []
    for node in _text_nodes(nodes):
        node.text, gone = _strip_markup(node.text)
        removed.extend(gone)
    return removed


def _filter_text(nodes: list[_Node], filters: Sequence[Callable[[str], str]]) -> None:
    """Run every filter over the document's text, and nothing else.

    A filter never sees a tag's attributes, another shortcode's output, or a raw element's
    content. HTML is held back too, by ``_HTML_TAG_RE``: it is the one kind of markup still
    sitting in text at this point, since platzky parses shortcodes but not HTML.
    """
    for node in _text_nodes(nodes):
        node.text = _filter_around_html(node.text, filters)


def _filter_around_html(text: str, filters: Sequence[Callable[[str], str]]) -> str:
    """Apply each filter to one node's text, keeping HTML tags out of their reach.

    Applied one filter at a time, so a filter's own output is held back from the next.
    """
    for transform in filters:
        parts = _HTML_TAG_RE.split(text)
        text = "".join(part if index % 2 else transform(part) for index, part in enumerate(parts))
    return text


def _render_node(node: _Node) -> str:
    """Render one node to HTML, innermost element first.

    An element's children are rendered one at a time rather than as a joined string, so
    the element can be told how many things it wrapped. Text between them is joined into
    ``content`` like everything else, but is not one of the children: a wrapper counts
    elements, which is what a stylesheet addresses.

    Args:
        node: The node to render.

    Returns:
        The node's HTML.
    """
    if isinstance(node, _Text):
        return node.text
    if isinstance(node, _RawElement):
        return _render_element(node.shortcode, node.raw_attrs, node.content, ())
    rendered = [(child, _render_node(child)) for child in node.children]
    content = "".join(html for _, html in rendered)
    children = tuple(
        Markup(html) for child, html in rendered if html and not isinstance(child, _Text)
    )
    return _render_element(node.shortcode, node.raw_attrs, content, children)


def _render(nodes: Sequence[_Node]) -> str:
    """Render parsed nodes to HTML, innermost element first."""
    return "".join(_render_node(node) for node in nodes)


def render_document(
    content: str,
    shortcodes: dict[str, Shortcode],
    filters: Sequence[Callable[[str], str]],
    *,
    strict: bool,
    strip_html: bool = False,
) -> tuple[str, list[str]]:
    """Parse the content once, strip and filter its text, then render its elements.

    The order is the point: a filter that ran after rendering would be handed markup an
    earlier shortcode produced, and stripping that ran before parsing could not tell HTML
    left in prose from HTML marked to keep inside a raw element.

    Args:
        content: The content to transform.
        shortcodes: Every shortcode permitted here, keyed by tag name.
        filters: Every permitted ``transform_text``, in pipeline order.
        strict: Whether a malformed tag is an error.
        strip_html: Whether to remove HTML the author wrote. Text nodes only; a raw
            element's content survives.

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
