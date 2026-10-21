"""Sanitizing of HTML an author wrote, so it can format content but never run script."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

import nh3

_TAGS = nh3.ALLOWED_TAGS | {"input"}

# Markdown task lists render as checkboxes, and ``class`` is how its output, and an
# author, ask the stylesheet for a look. ``style`` stays out, but for the alignment
# Markdown writes on table cells: a post styles itself through its own ``css`` field.
_GENERIC_ATTRIBUTES = {"class", "lang", "title"}
_ATTRIBUTES = {
    **nh3.ALLOWED_ATTRIBUTES,
    "*": _GENERIC_ATTRIBUTES,
    "input": {"checked", "disabled"},
    "th": nh3.ALLOWED_ATTRIBUTES["th"] | {"style"},
    "td": nh3.ALLOWED_ATTRIBUTES["td"] | {"style"},
}

_ATTRIBUTE_VALUES = {"input": {"type": {"checkbox"}}}

_STYLE_PROPERTIES = {"text-align"}

_URL_ATTRIBUTES = {"href", "src", "cite"}


class ContentNotAllowed(ValueError):
    """HTML in content uses a tag, attribute or URL that content may not have.

    Raised rather than removed quietly, so the author learns what is not an option instead
    of finding it gone. Like a malformed shortcode, it fails the render.
    """


def _is_attribute_allowed(tag: str, name: str, value: str) -> bool:
    """Whether a tag may carry this attribute with this value.

    Args:
        tag: The tag carrying the attribute.
        name: The attribute's name.
        value: The attribute's value, entities resolved.

    Returns:
        True if the sanitizer would keep the attribute as written.
    """
    allowed_values = _ATTRIBUTE_VALUES.get(tag, {}).get(name)
    return (
        value in allowed_values
        if allowed_values is not None
        else (
            name in _GENERIC_ATTRIBUTES
            or (
                name in _ATTRIBUTES.get(tag, set())
                and (name != "style" or _is_style_allowed(value))
            )
        )
    )


def _is_style_allowed(value: str) -> bool:
    """Whether every declaration in a ``style`` value sets an allowed property."""
    declarations = [d for d in value.split(";") if d.strip()]
    return all(d.split(":")[0].strip().lower() in _STYLE_PROPERTIES for d in declarations)


def _url_scheme(value: str) -> str:
    """The scheme of a URL, empty for a relative one."""
    return urlsplit(value.strip()).scheme.lower()


def _offence(tag: str, attrs: list[tuple[str, str | None]]) -> str | None:
    """Describe what in one tag content may not have.

    Args:
        tag: The tag's name.
        attrs: The tag's attributes, entities resolved; a bare attribute has no value.

    Returns:
        A description of the first thing not allowed, or None if the tag is allowed.
    """
    values = [(name, value or "") for name, value in attrs]
    schemes = [(name, _url_scheme(value)) for name, value in values if name in _URL_ATTRIBUTES]
    offences = (
        [f"<{tag}> is not allowed"]
        if tag not in _TAGS
        else [
            f'attribute "{name}" on <{tag}> is not allowed'
            for name, value in values
            if not _is_attribute_allowed(tag, name, value)
        ]
        + [
            f'"{scheme}:" links in "{name}" on <{tag}> are not allowed'
            for name, scheme in schemes
            if scheme and scheme not in nh3.ALLOWED_URL_SCHEMES
        ]
    )
    return offences[0] if offences else None


class _AllowlistChecker(HTMLParser):
    """Raise on the first tag, attribute or URL in a document that content may not have."""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Check an opening tag.

        Raises:
            ContentNotAllowed: If the tag, one of its attributes, or a URL in one is not
                allowed.
        """
        if (offence := _offence(tag, attrs)) is not None:
            raise ContentNotAllowed(offence)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Check a self-closing tag, as an opening one.

        Raises:
            ContentNotAllowed: If the tag, one of its attributes, or a URL in one is not
                allowed.
        """
        self.handle_starttag(tag, attrs)


def sanitize_html(html: str) -> str:
    """Refuse HTML content may not have, and return the rest in canonical form.

    The check is what an author sees. Cleaning what passed it is a second line, in case
    the check and the cleaner ever disagree about what a piece of HTML means.

    Args:
        html: HTML an author wrote, or that was rendered from what they wrote.

    Returns:
        The HTML as the cleaner serializes it, comments removed.

    Raises:
        ContentNotAllowed: If the HTML has a tag, attribute or URL that is not allowed,
            such as ``<script>``, an ``onclick`` handler or a ``javascript:`` link.
    """
    checker = _AllowlistChecker()
    checker.feed(html)
    checker.close()
    return nh3.clean(
        html,
        tags=_TAGS,
        attributes=_ATTRIBUTES,
        tag_attribute_values=_ATTRIBUTE_VALUES,
        filter_style_properties=_STYLE_PROPERTIES,
        link_rel=None,
    )
