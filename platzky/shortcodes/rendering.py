"""Shortcode rendering — the document machinery behind ``transform_content``.

A document is parsed once into nodes, then walked twice — strip, render — so no pass ever
sees what a later one produces. Rendering formats and filters the author's text, with
each shortcode's output held out of both. ``render_document`` is the whole public
surface; everything else here serves it.
"""

from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from markupsafe import Markup, escape

from platzky.shortcodes.nodes import Element, Node, RawElement, Text
from platzky.shortcodes.parser import parse, strip_text_nodes
from platzky.shortcodes.shortcode import ChildPolicy, ElementRefused, Shortcode
from platzky.text_format import HTML, TextFormat

logger = logging.getLogger(__name__)


#: An HTML tag, held back from text filters.
#:
#: Quote-aware, because ``>`` is legal inside an attribute: ``<[^>]*>`` ends
#: ``<a title="a > b">`` at the first ``>`` and hands ``` b">`` to every filter, which the
#: filter contract says never happens. Same hazard the parser's stripper avoids.
_HTML_TAG = r"""<(?:[^>"']|"[^"]*"|'[^']*')*>"""

_MAX_ATTR_NAME_LEN = 100
_MAX_ATTR_VALUE_LEN = 2048
_ATTR_RE = re.compile(rf'([\w-]{{1,{_MAX_ATTR_NAME_LEN}}})="([^"]{{0,{_MAX_ATTR_VALUE_LEN}}})"')


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
        attrs = shortcode.attributes.accept(dict(_ATTR_RE.findall(raw_attrs)))
        # Markup truthfully: the content was either vouched for by its caller or escaped at
        # the boundary, and anything added since came from a permitted plugin. The type is
        # what tells a shortcode author not to escape it again.
        return shortcode.render(attrs, Markup(content), children)
    except ElementRefused as refusal:
        # One element, not the page: an author's typo costs its own tag. Logged because an
        # author cannot see an absence, and named by tag so they can find which one.
        logger.warning("[%s] rendered nothing: %s.", shortcode.name, refusal)
        return ""


def _filter_around(
    text: str, filters: Sequence[Callable[[str], str]], held_back: re.Pattern[str]
) -> str:
    """Apply each filter to the text, keeping what ``held_back`` matches out of their reach.

    Applied one filter at a time, so a filter's own output is held back from the next.

    Args:
        text: HTML whose text the filters may change.
        filters: Every permitted ``transform_text``, in pipeline order.
        held_back: One capturing group matching what no filter may see.

    Returns:
        The text after every filter has run.
    """
    for transform in filters:
        parts = held_back.split(text)
        parts[::2] = [transform(part) for part in parts[::2]]  # the text between matches
        text = "".join(parts)
    return text


def _is_child_allowed(child: Node, policy: ChildPolicy) -> bool:
    """Whether a child is one its parent's ``child_policy`` allows.

    Args:
        child: The child node to judge.
        policy: What the parent accepts between its tags.

    Returns:
        True if the child may stay. Whitespace text is allowed whatever the policy — it is
        how an author lays tags out over several lines, not something they wrote.
    """
    return (
        (not child.text.strip() or policy.is_text_allowed())
        if isinstance(child, Text)
        else policy.is_tag_allowed(child.shortcode.name)
    )


def _disallowed_children(node: Element) -> tuple[Node, ...]:
    """Collect the children an element's ``child_policy`` does not allow.

    Args:
        node: The element to check, with its children still parsed rather than rendered.

    Returns:
        Every offending child, in document order. Empty when the policy accepts everything
        the element holds.
    """
    policy = node.shortcode.child_policy
    return tuple(child for child in node.children if not _is_child_allowed(child, policy))


def _describe_child(child: Node) -> str:
    """Name a child the way a refusal message should, for an author reading the log."""
    return (
        f"text {child.text.strip()[:30]!r}"
        if isinstance(child, Text)
        else f"[{child.shortcode.name}]"
    )


@dataclass(frozen=True)
class _TextWithPlaceholders:
    """The author's text with a placeholder where each element was, and what each stands for.

    Each placeholder carries a number, its element's position in ``elements`` and
    ``outputs``: ``<platzky-shortcode-…-0>`` stands for the first.

    Attributes:
        text: The author's text, a placeholder in each element's place.
        elements: The elements, shown as written where a placeholder lands in code.
        outputs: Each element's rendered output, put back in its placeholder's place.
    """

    text: str
    elements: list[RawElement | Element]
    outputs: list[str]


def _as_written(element: RawElement | Element) -> str:
    """The element in shortcode syntax, as an author would write it."""
    name = element.shortcode.name
    inner = (
        element.content
        if isinstance(element, RawElement)
        else "".join(_node_as_written(child) for child in element.children)
    )
    closing = "" if element.shortcode.kind == "void" else f"[/{name}]"
    return f"[{name}{element.raw_attrs}]{inner}{closing}"


def _node_as_written(node: Node) -> str:
    """The node in the syntax an author would write it in."""
    return node.text if isinstance(node, Text) else _as_written(node)


class _Renderer:
    """Renders one document: the author's text formatted and filtered, elements as rendered.

    Shortcode output is code's, not the author's, so it must reach neither the text format
    nor a filter. The sibling nodes at each level of nesting all go the same way:
    each element is rendered and a placeholder stands in its place, the author's text is
    formatted and filtered, then each placeholder is replaced by its element's output. The
    nonce in the placeholders keeps an author from writing one of their own.
    """

    def __init__(self, text_format: TextFormat, filters: Sequence[Callable[[str], str]]):
        self._text_format = text_format
        self._filters = filters
        self._prefix = f"platzky-shortcode-{secrets.token_hex(8)}-"
        # A placeholder inside code is escaped to text, so it is held back by name as well.
        # One group, so ``split`` returns what is held back at the odd indices.
        self._held_back = re.compile(rf"({_HTML_TAG}|&lt;{re.escape(self._prefix)}\d+&gt;)")

    def render_document(self, nodes: Sequence[Node]) -> str:
        """Render a document's top level: the author's text as blocks, elements as rendered."""
        with_placeholders = self._replace_elements_with_placeholders(nodes)
        html = self._to_html(with_placeholders.text)
        return self._put_back_elements(html, with_placeholders)

    def _render_node(self, node: RawElement | Element) -> str:
        """Render one element to HTML, innermost element first.

        An element's children are rendered one at a time rather than as a joined string, so
        the element can be told how many things it wrapped. Text between them is joined into
        ``content`` like everything else, but is not one of the children: a wrapper counts
        elements, which is what a stylesheet addresses.

        Args:
            node: The element to render.

        Returns:
            The element's HTML.
        """
        if isinstance(node, RawElement):
            return _render_element(node.shortcode, node.raw_attrs, node.content, ())
        if disallowed := _disallowed_children(node):
            # Refused whole rather than per child: dropping only the offenders would leave a
            # wrapper whose structure the author still got wrong, rendered as if it were
            # right. Every offender is named, so one log line is one trip back to the content.
            logger.warning(
                "[%s] rendered nothing: it accepts %s, and holds %s.",
                node.shortcode.name,
                node.shortcode.child_policy.allowed,
                ", ".join(_describe_child(child) for child in disallowed),
            )
            return ""
        content, outputs = self._render_children(node.children)
        children = tuple(Markup(html) for html in outputs if html)
        return _render_element(node.shortcode, node.raw_attrs, content, children)

    def _render_children(self, nodes: Sequence[Node]) -> tuple[str, list[str]]:
        """Render what an element wraps: the author's text formatted, elements as rendered.

        Text inside an element is formatted inline, so a link's text gets no ``<p>`` of its
        own, unless the author wrote paragraphs there, separated by a blank line.

        Args:
            nodes: The element's children, in document order.

        Returns:
            The children's HTML, and each element child's output in document order.
        """
        with_placeholders = self._replace_elements_with_placeholders(nodes)
        has_text = any(isinstance(node, Text) and node.text.strip() for node in nodes)
        # Whitespace between an element's children is layout, not prose: formatting it would
        # turn an indented child into a Markdown code block.
        text = with_placeholders.text
        html = self._format_children_text(text) if has_text else text
        return self._put_back_elements(html, with_placeholders), with_placeholders.outputs

    def _format_children_text(self, source: str) -> str:
        """Format an element's text inline, or as blocks when the author wrote paragraphs."""
        to_html = self._to_html if re.search(r"\n[ \t]*\n", source) else self._to_inline_html
        return to_html(source)

    def _replace_elements_with_placeholders(self, nodes: Sequence[Node]) -> _TextWithPlaceholders:
        """Render each element among the siblings and put a placeholder in its place."""
        outputs: list[str] = []
        elements: list[RawElement | Element] = []
        text = ""
        for node in nodes:
            if isinstance(node, Text):
                text += node.text
            else:
                text += self._placeholder(len(outputs))
                outputs.append(self._render_node(node))
                elements.append(node)
        return _TextWithPlaceholders(text, elements, outputs)

    def _placeholder(self, index: int) -> str:
        """The tag standing in for the siblings' ``index``-th element while its text is formatted.

        A tag rather than text, so a shortcode alone on a line reaches a Markdown renderer
        as an HTML block, not as a paragraph that would wrap its output in ``<p>``.
        """
        return f"<{self._prefix}{index}>"

    def _to_html(self, source: str) -> str:
        """Format and filter the siblings' text as blocks, leaving each placeholder where it was.

        Filters run last, on what the reader will see rather than on the author's syntax.
        HTML tags and placeholders, escaped ones too, are held back from them, so a filter never
        sees a tag's attributes or another shortcode's output.

        Args:
            source: The siblings' text with a placeholder for each element.

        Returns:
            HTML, still holding the placeholders.
        """
        formatted = self._text_format.to_html(self._end_placeholder_blocks(source))
        return _filter_around(formatted, self._filters, self._held_back)

    def _to_inline_html(self, source: str) -> str:
        """Format and filter the siblings' text without block structure, as ``_to_html`` does.

        Args:
            source: The siblings' text with a placeholder for each element.

        Returns:
            Inline HTML, still holding the placeholders.
        """
        formatted = self._text_format.to_inline_html(source)
        return _filter_around(formatted, self._filters, self._held_back)

    def _put_back_elements(self, html: str, with_placeholders: _TextWithPlaceholders) -> str:
        """Put each element's output where its placeholder is.

        A placeholder the format escaped sat inside code, such as a Markdown code span or
        block, where the author is showing a shortcode rather than using one, so it gets
        the shortcode as they wrote it.

        Args:
            html: The siblings' formatted HTML, holding the placeholders.
            with_placeholders: What the HTML was formatted from, for each placeholder's
                element and output.

        Returns:
            The HTML with no placeholder left.
        """
        prefix = re.escape(self._prefix)
        shown = re.sub(
            rf"&lt;{prefix}(\d+)&gt;",
            lambda match: str(escape(_as_written(with_placeholders.elements[int(match.group(1))]))),
            html,
        )
        return re.sub(
            rf"<{prefix}(\d+)>", lambda match: with_placeholders.outputs[int(match.group(1))], shown
        )

    def _end_placeholder_blocks(self, source: str) -> str:
        """Put a blank line after each placeholder that starts a block alone on its line.

        Such a line opens a CommonMark HTML block, which only a blank line ends, so the
        author's next line would otherwise be passed through as HTML, unformatted. A
        placeholder continuing a paragraph opens no block and is left as it is.
        """
        alone = re.compile(rf" {{0,3}}<{re.escape(self._prefix)}\d+>[ \t]*")
        lines: list[str] = []
        starts_block = True
        held_open = False
        for line in source.split("\n"):
            if held_open and line.strip():
                lines.append("")
                starts_block = True
            held_open = starts_block and bool(alone.fullmatch(line))
            starts_block = held_open or not line.strip()
            lines.append(line)
        return "\n".join(lines)


def render_document(
    content: str,
    shortcodes: dict[str, Shortcode],
    filters: Sequence[Callable[[str], str]],
    *,
    strict: bool,
    strip_html: bool = False,
    text_format: TextFormat = HTML,
) -> tuple[str, list[str]]:
    """Parse the content once, strip its text, then render it.

    The order is the point: stripping that ran before parsing could not tell HTML left in
    prose from HTML marked to keep inside a raw element. Formatting and filtering happen
    while rendering, on the author's text only, with each shortcode's output held out of
    both — a filter is never handed markup a shortcode produced.

    Args:
        content: The content to transform.
        shortcodes: Every shortcode permitted here, keyed by tag name.
        filters: Every permitted ``transform_text``, in pipeline order.
        strict: Whether a malformed tag is an error.
        strip_html: Whether to remove HTML the author wrote. Text nodes only; a raw
            element's content survives.
        text_format: The format the author's text is written in. Raw element content is
            not formatted.

    Returns:
        The rendered content, and the names of the HTML tags stripped from it.

    Raises:
        ShortcodeError: If ``strict`` and a shortcode tag is malformed.
    """
    nodes: list[Node] = parse(content, shortcodes, strict=strict) if shortcodes else [Text(content)]
    removed = strip_text_nodes(nodes) if strip_html else []
    return _Renderer(text_format, filters).render_document(nodes), removed
