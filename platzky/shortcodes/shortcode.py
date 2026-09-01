"""Shortcode parser for blog post content.

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
"""

import inspect
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar, Literal, cast, final, get_args

from markupsafe import Markup, escape

_VALID_SHORTCODE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")

#: How a shortcode is written, which is what tells the parser what to do with the text
#: after the opening tag. ``"block"`` wraps content and must be closed; ``"void"`` takes
#: none and must not be; ``"raw"`` must be closed, and its body is taken verbatim rather
#: than parsed, so brackets inside it are characters rather than syntax.
#:
#: The kind is a *declaration*, read before the parser descends, which is what lets it
#: change parsing at all — ``render`` runs afterwards and so could never stop it.
#:
#: A raw body is verbatim against the whole pipeline: no plugin's text filter reaches into
#: it and no plugin's shortcodes are rendered inside it, because the document is parsed
#: once before any of them run.
ShortcodeKind = Literal["block", "void", "raw"]

#: The same set at runtime, for the check in ``__init_subclass__`` — plugin authors are
#: third parties who may not run a type checker. Derived rather than repeated so adding a
#: kind is one edit.
_SHORTCODE_KINDS: frozenset[str] = frozenset(get_args(ShortcodeKind))


class ShortcodeError(ValueError):
    """Raised when content cannot be parsed as the shortcodes registered for it describe.

    A ``ValueError`` because the content is the bad input. It carries the tag name and the
    offset it was written at: this surfaces as a failed page render, so the log is the
    only evidence an operator gets of which bracket was wrong.
    """

    def __init__(self, message: str, tag: str, position: int) -> None:
        """Record which tag failed and where.

        Args:
            message: What went wrong, phrased for whoever wrote the content.
            tag: Name of the shortcode tag at fault.
            position: Character offset of the tag within the content.
        """
        super().__init__(f"{message} (shortcode {tag!r} at character {position})")
        self.tag = tag
        self.position = position


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

    #: Whether a closing tag is expected. The default wraps content, because most
    #: shortcodes do and because it is the safe default to get wrong: a block shortcode
    #: mistakenly left as ``"block"`` still renders, whereas a void one declared ``"block"``
    #: makes every correct use of it look unclosed. Declare ``"void"`` for a tag written
    #: without a closing tag, like ``[image url="…"]`` — the parser then renders it on
    #: sight, and rejects an unclosed ``"block"`` tag rather than guessing what was meant.
    kind: ClassVar[ShortcodeKind] = "block"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        name = getattr(cls, "name", None)
        if not isinstance(name, str) or not _VALID_SHORTCODE_NAME_RE.match(name):
            raise ValueError(
                f"Shortcode subclass {cls.__name__!r} must declare a valid `name`; got {name!r}."
            )
        kind = getattr(cls, "kind", None)
        if kind not in _SHORTCODE_KINDS:
            raise ValueError(
                f"Shortcode subclass {cls.__name__!r} declares `kind` {kind!r}; "
                f"expected one of {sorted(_SHORTCODE_KINDS)}."
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
