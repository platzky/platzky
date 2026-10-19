"""Shortcode parsing — reading a document into nodes, and stripping HTML from its text.

Shortcodes nest, including inside another of the same name: tags are matched with a stack,
so a closing tag pairs with the opening tag it belongs to rather than the nearest one.
How the nodes are then rendered lives in :mod:`platzky.shortcodes.rendering`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser

from platzky.shortcodes.nodes import Element, Node, RawElement, Text
from platzky.shortcodes.shortcode import Shortcode, ShortcodeError


@dataclass
class _Frame:
    """An element the parser has opened and not yet closed.

    The bottom frame is the document itself, so appending to ``stack[-1]`` needs no special
    case for top level; its name is ``""``, which no shortcode can have.
    """

    name: str
    raw_attrs: str
    children: list["Node"]

    #: Where the opening tag was written, carried only so an unclosed element can say which
    #: one it was.
    position: int


def _tag_pattern(shortcodes: dict[str, Shortcode]) -> re.Pattern[str]:
    """Match an opening or closing tag of a known shortcode, grouped (close, open, attrs)."""
    names = "|".join(re.escape(n) for n in shortcodes)
    return re.compile(rf"\[/({names})\]|\[({names})((?:\s+[\w-]+=\"[^\"]*\")*)\s*\]")


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
        stack[-1].children.append(Element(shortcodes[frame.name], frame.raw_attrs, []))
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
        stack[-1].children.append(Text(match.group(0)))
        return
    _discharge_unclosed_above(stack, depth, shortcodes, strict=strict)
    frame = stack.pop()
    stack[-1].children.append(Element(shortcodes[frame.name], frame.raw_attrs, frame.children))


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
        stack[-1].children.append(Element(shortcode, raw_attrs, []))
        return after_tag
    if shortcode.kind == "raw":
        end = content.find(f"[/{name}]", after_tag)
        if end < 0:
            if strict:
                raise ShortcodeError(_never_closed(name), name, match.start())
            stack[-1].children.append(Text(match.group(0)))
            return after_tag
        stack[-1].children.append(RawElement(shortcode, raw_attrs, content[after_tag:end]))
        return end + len(name) + 3
    stack.append(_Frame(name, raw_attrs, [], match.start()))
    return after_tag


def parse(content: str, shortcodes: dict[str, Shortcode], *, strict: bool) -> list[Node]:
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
            stack[-1].children.append(Text(content[position : match.start()]))
        position = match.end()
        closing, opening = match.group(1), match.group(2)
        if closing is not None:
            _close_element(stack, match, closing, shortcodes, strict=strict)
        else:
            position = _open_element(stack, content, match, opening, shortcodes, strict=strict)

    if position < len(content):
        stack[-1].children.append(Text(content[position:]))
    _discharge_unclosed_above(stack, 0, shortcodes, strict=strict)
    return stack[0].children


def _text_nodes(nodes: Sequence[Node]) -> Iterator[Text]:
    """Yield every text node, never descending into a ``RawElement``.

    The one definition of what the text passes reach, so "raw content is verbatim" is a
    property of the walk rather than a rule each pass has to remember.
    """
    for node in nodes:
        if isinstance(node, Text):
            yield node
        elif isinstance(node, Element):
            yield from _text_nodes(node.children)


def strip_text_nodes(nodes: list[Node]) -> list[str]:
    """Remove HTML from the document's text, returning the tag names removed."""
    removed: list[str] = []
    for node in _text_nodes(nodes):
        node.text, gone = _strip_markup(node.text)
        removed.extend(gone)
    return removed
