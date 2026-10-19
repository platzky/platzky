"""The nodes a shortcode document is parsed into: the author's text and the elements in it.

For example, with ``link`` a block shortcode and ``html`` a raw one::

    Hi [link url="/a"]**there**[/link] [html]<b>x</b>[/html]

parses into::

    [
        Text("Hi "),
        Element(link, raw_attrs=' url="/a"', children=[Text("**there**")]),
        Text(" "),
        RawElement(html, raw_attrs="", content="<b>x</b>"),
    ]
"""

from __future__ import annotations

from dataclasses import dataclass

from platzky.shortcodes.shortcode import Shortcode


@dataclass
class Text:
    """The author's own text, at the top level or inside an element.

    Holds everything that is not a registered shortcode tag: prose, Markdown, HTML, and
    brackets no shortcode claims. ``Hi <b>there</b> [unknown]`` is one ``Text`` as written.

    The only node a filter may touch and the only one ``STRIP_CONTENT_HTML`` reaches —
    including the text inside an element, so ``[hero]<b>x</b>[/hero]`` loses its ``<b>``.
    """

    text: str


@dataclass
class RawElement:
    """A ``"raw"`` element: its content is the characters between the tags, unparsed.

    ``[html]<b>[link]x[/link]</b>[/html]`` has ``raw_attrs=""`` and
    ``content="<b>[link]x[/link]</b>"``: the ``[link]`` inside stays text, never parsed.

    A string rather than nodes because the parser never descended into it — which is what
    keeps it verbatim against filters and against ``STRIP_CONTENT_HTML``.
    """

    shortcode: Shortcode

    #: The attributes as written in the opening tag, leading space included.
    raw_attrs: str
    content: str


@dataclass
class Element:
    """A shortcode element whose content was parsed into nodes.

    ``[link url="/a" title="A"]go **now**[/link]`` has ``raw_attrs=' url="/a" title="A"'``
    and ``children=[Text("go **now**")]``. A nested element is a child of its own:
    ``[slideshow][figure image="/a.jpg"][/figure][/slideshow]`` holds one ``Element``.

    Every kind but ``"raw"`` ends up here; a ``"void"`` shortcode such as
    ``[image url="/a.png"]`` simply has no children.
    """

    shortcode: Shortcode

    #: The attributes as written in the opening tag, leading space included.
    raw_attrs: str
    children: list["Node"]


Node = Text | RawElement | Element
