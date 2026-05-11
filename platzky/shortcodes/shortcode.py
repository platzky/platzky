"""Shortcode parser for blog post content.

Plugins register handlers via ContentTransformerPluginBase.get_supported_shortcodes().
Syntax:
    Block: [tagname attr="val"]content[/tagname]
    Void:  [tagname attr="val"]

Nested shortcodes of different tag names work; nested same-tag shortcodes do not
(the lazy regex finds the nearest closing tag).
"""

import inspect
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar

_VALID_SHORTCODE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


@dataclass
class ShortcodeAttr:
    """Descriptor for a single shortcode attribute."""

    name: str
    description: str
    required: bool = False


class ShortcodeAttrs:
    """Attribute schema and parsed values for a shortcode tag.

    Used as a class variable to declare the schema (iterable for the help page)
    and as the ``attrs`` argument to ``Shortcode.render`` populated with parsed values.
    """

    def __init__(self, attrs: list[ShortcodeAttr]) -> None:
        """Initialise with a schema.

        Args:
            attrs: Attribute schema defining names, descriptions, and defaults.
        """
        self._schema: dict[str, ShortcodeAttr] = {a.name: a for a in attrs}
        self._values: dict[str, str] = {}

    def __iter__(self) -> Iterator[ShortcodeAttr]:
        """Iterate over the attribute schema (for the help-page template)."""
        return iter(self._schema.values())

    def __bool__(self) -> bool:
        """Return True if the schema declares any attributes."""
        return bool(self._schema)

    def __getattr__(self, name: str) -> str:
        """Return the parsed value, falling back to the declared default.

        Args:
            name: Attribute name to look up.

        Returns:
            Parsed value, or the declared default, or empty string.

        Raises:
            AttributeError: If name is not in the schema.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._values:
            return self._values[name]
        if name in self._schema:
            return ""
        raise AttributeError(f"No shortcode attribute {name!r}")

    def __eq__(self, other: object) -> bool:
        """Support comparison with plain dicts for test assertions.

        Args:
            other: A dict or ShortcodeAttrs to compare against.

        Returns:
            True if the parsed values match; NotImplemented for other types.
        """
        if isinstance(other, dict):
            return self._values == other
        if isinstance(other, ShortcodeAttrs):
            return self._values == other._values
        return NotImplemented

    def __repr__(self) -> str:
        """Return a readable representation showing schema keys and values."""
        return f"ShortcodeAttrs({list(self._schema)!r}, values={self._values!r})"


class Shortcode(ABC):
    """Base class for a registered shortcode tag. Subclass and implement ``render``."""

    name: str
    description: str
    attributes: ClassVar[ShortcodeAttrs] = ShortcodeAttrs([])
    example: str = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        name = getattr(cls, "name", None)
        if not isinstance(name, str) or not _VALID_SHORTCODE_NAME_RE.match(name):
            raise ValueError(
                f"Shortcode subclass {cls.__name__!r} must declare a valid `name`; got {name!r}."
            )

    @abstractmethod
    def render(self, attrs: ShortcodeAttrs, content: str) -> str:
        """Render the shortcode tag and return the replacement HTML.

        Args:
            attrs: Parsed shortcode attributes with dot-access and default fallback.
            content: Inner content between opening and closing tags.

        Returns:
            Replacement HTML string.
        """
