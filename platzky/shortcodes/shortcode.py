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
from typing import ClassVar, cast, final

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
        self.values: dict[str, str] = {}

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
        if name in self.values:
            return self.values[name]
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
            return self.values == other
        if isinstance(other, ShortcodeAttrs):
            return self.values == other.values
        return NotImplemented

    def __repr__(self) -> str:
        """Return a readable representation showing schema keys and values."""
        return f"ShortcodeAttrs({list(self._schema)!r}, values={self.values!r})"

    __hash__ = None  # type: ignore[assignment]


class Shortcode(ABC):
    """Base class for a registered shortcode tag. Subclass and implement ``render``."""

    name: str
    description: str
    attributes: ClassVar[ShortcodeAttrs] = ShortcodeAttrs([])
    example: str = ""

    #: Key holding the inner content when a field value is a dict — the field equivalent
    #: of what an author writes between the tags. Declare it when a shortcode names that
    #: key something of its own (``"code"``, ``"url"``); ``"value"`` is always accepted
    #: as well, so an application storing a bare value needs no declaration.
    content_key: ClassVar[str] = "content"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        name = getattr(cls, "name", None)
        if not isinstance(name, str) or not _VALID_SHORTCODE_NAME_RE.match(name):
            raise ValueError(
                f"Shortcode subclass {cls.__name__!r} must declare a valid `name`; got {name!r}."
            )

    @final
    def render_value(self, value: object) -> str:
        """Render a stored value to HTML, the same way the shortcode renders a tag.

        Called when the application has a stored value mapped to this shortcode rather
        than a tag written in prose — for example the string ``"SUMMER24"`` kept against a
        record. The application displays the result directly, so it needs no per-shortcode
        frontend code; one wanting the value as data instead reads the entry itself, using
        ``content_key`` to know which key a bare value belongs under.

        Not overridable, and deliberately: a shortcode has exactly one rendering, in
        ``render``, and this maps a field value onto that method's arguments rather than
        offering a second place to write one. Keys matching declared ``attributes``
        become attributes, ``content_key`` (or ``value``) becomes the inner content, and
        a scalar value becomes the inner content on its own. A shortcode adapts by
        *declaring* — naming its ``content_key``, adding a ``ShortcodeAttr`` — so the two
        renderings cannot drift apart.

        Escaping is ``render``'s responsibility, exactly as for a tag written by an
        author — a field value is data and can be hostile.

        Args:
            value: The stored value, as the application holds it.

        Returns:
            HTML for the value.
        """
        attrs = ShortcodeAttrs(list(self.attributes))
        if isinstance(value, dict):
            d = cast(dict[str, object], value)
            declared = {a.name for a in self.attributes}
            attrs.values = {k: str(v) for k, v in d.items() if k in declared and v is not None}
            content = d.get(self.content_key, d.get("value", ""))
        else:
            content = value
        return self.render(attrs, "" if content is None else str(content))

    @abstractmethod
    def render(self, attrs: ShortcodeAttrs, content: str) -> str:
        """Render the shortcode tag and return the replacement HTML.

        Args:
            attrs: Parsed shortcode attributes with dot-access and default fallback.
            content: Inner content between opening and closing tags.

        Returns:
            Replacement HTML string.
        """
