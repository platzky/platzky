"""The nodes a shortcode document is parsed into: the author's text and the elements in it."""

from __future__ import annotations

from dataclasses import dataclass

from platzky.shortcodes.shortcode import Shortcode


@dataclass
class Text:
    """Text outside any shortcode element, including HTML and unregistered brackets.

    The only node a filter may touch and the only one ``STRIP_CONTENT_HTML`` reaches.
    """

    text: str


@dataclass
class RawElement:
    """A ``"raw"`` element: its content is the characters between the tags, unparsed.

    A string rather than nodes because the parser never descended into it — which is what
    keeps it verbatim against filters and against ``STRIP_CONTENT_HTML``.
    """

    shortcode: Shortcode
    raw_attrs: str
    content: str


@dataclass
class Element:
    """A shortcode element whose content was parsed into nodes.

    Every kind but ``"raw"`` ends up here; a ``"void"`` shortcode simply has no children.
    """

    shortcode: Shortcode
    raw_attrs: str
    children: list["Node"]


Node = Text | RawElement | Element
