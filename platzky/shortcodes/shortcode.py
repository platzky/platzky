"""Shortcode parser for blog post content.

Plugins register handlers via ContentFilterBase.get_content_tags().
Syntax:
    Block: [tagname attr="val"]content[/tagname]
    Void:  [tagname attr="val"]

Nested shortcodes of different tag names work; nested same-tag shortcodes do not
(the lazy regex finds the nearest closing tag).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

_ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


@dataclass
class ShortcodeAttr:
    """Descriptor for a single shortcode attribute."""

    name: str
    description: str
    required: bool = False
    default: str | None = None


@dataclass
class Shortcode:
    """Descriptor for a registered shortcode tag."""

    name: str
    handler: Callable[[dict[str, str], str], str]
    description: str
    attributes: list[ShortcodeAttr] = field(default_factory=list)
    has_content: bool = False
    example: str = ""


def make_shortcode_applier(shortcodes: dict[str, Shortcode]) -> Callable[[str], str]:
    """Return a callable that applies all registered shortcodes to a content string.

    Compiles the regex once at call time so repeated application is cheap.
    Returns the identity function when no shortcodes are registered.
    """
    if not shortcodes:
        return lambda content: content

    tag_names = "|".join(re.escape(n) for n in shortcodes)
    pattern = re.compile(
        rf"\[({tag_names})((?:\s+[\w-]+=\"[^\"]*\")*)\s*\](?:(.*?)\[/\1\])?",
        re.DOTALL,
    )

    def _apply(content: str) -> str:
        """Replace registered shortcode tags in content with handler output."""

        def _replace(m: re.Match[str]) -> str:
            """Dispatch a matched shortcode tag to its registered handler."""
            attrs = dict(_ATTR_RE.findall(m.group(2) or ""))
            inner = m.group(3) or ""
            return shortcodes[m.group(1)].handler(attrs, inner)

        return pattern.sub(_replace, content)

    return _apply


def apply_shortcodes(content: str, shortcodes: dict[str, Shortcode]) -> str:
    """Replace registered shortcode tags in content with handler output.

    Unregistered tags are passed through unchanged.
    Prefer ``make_shortcode_applier`` when applying repeatedly to amortise
    regex compilation.
    """
    return make_shortcode_applier(shortcodes)(content)
