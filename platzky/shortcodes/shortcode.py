"""Shortcode parser for blog post content.

Plugins register handlers through the ``shortcodes`` class variable on
``ContentTransformerPluginBase``. Syntax::

    [tagname attr="val"]                     # void
    [tagname attr="val"]content[/tagname]    # block

Shortcodes nest, including inside another of the same name: tags are matched with a
stack, so a closing tag pairs with the opening tag it belongs to rather than the nearest
one. A closing tag with nothing to close, and a tag name no plugin registered, are left
in the content as the author wrote them. An opening tag that is never closed renders
with empty content, which is also how a tag written without one — ``[image url="…"]`` —
is handled.
"""

import inspect
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar, cast, final

from markupsafe import Markup, escape

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

        A stored value is data and can be hostile, and nobody vouched for it, so it is
        escaped here — the same rule ``transform_content`` applies to content nobody
        vouched for. ``render`` therefore embeds its content directly and never escapes
        it, on either path.

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
        # str() would strip the Markup and make a shortcode that still escapes
        # double-escape; escape() keeps it, so such a shortcode gets a harmless no-op.
        return self.render(attrs, escape("" if content is None else content))

    @abstractmethod
    def render(self, attrs: ShortcodeAttrs, content: Markup) -> str:
        """Render the shortcode tag and return the replacement HTML.

        **Embed ``content`` directly; never escape it.** Its type says why: ``Markup``
        means the escaping decision is already made. Every character in it is either one
        an untrusted source supplied — in which case the boundary already turned it into
        an entity, and there is nothing left to neutralise — or one a trusted source meant
        to render, written by an author with write access or produced by a plugin
        permitted for this content type. So escaping here cannot add safety; it can only
        turn markup that was meant into literal ``&lt;span&gt;`` on the page.

        **Escape every attribute where you interpolate it.** Attributes stay raw, because
        that escaping is an HTML-attribute-context obligation rather than a trust
        judgement, and it applies just as much to a value an author typed.

        A subclass may still annotate ``content`` as ``str`` — widening a parameter is
        allowed — and escaping it is a harmless no-op on a ``Markup``. The rule is
        therefore about keeping meaning, not about safety. One caveat: ``Markup``
        overloads ``+``, ``%`` and ``format`` to escape their *other* operand, so build
        output with f-strings rather than concatenation or ``.format()``.

        Args:
            attrs: Parsed shortcode attributes with dot-access and default fallback. Raw —
                escape at the point of use.
            content: Inner content between opening and closing tags. Already safe to embed.

        Returns:
            Replacement HTML string.
        """
