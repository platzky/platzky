"""What a route contributes to ``sitemap.xml``, declared with its ``sitemap`` route option."""

import typing as t
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class SitemapEntry:
    """One URL of a route in the sitemap.

    Attributes:
        values: The route's URL variables for this URL, e.g. ``{"post_slug": "the-hobbit"}``;
            empty for a route without variables.
        lastmod: When the page last changed, if known.
    """

    values: Mapping[str, str] = field(default_factory=dict[str, str])
    lastmod: date | None = None


SitemapEntries = Callable[[str], Iterable[SitemapEntry]]
"""Returns a route's sitemap entries in the language it is given."""


def single_url(_lang: str) -> list[SitemapEntry]:
    """List the one URL of a route without variables, in any language."""
    return [SitemapEntry()]


def sitemap_entries_for(
    rule: str, methods: Iterable[str] | None, sitemap: object
) -> SitemapEntries:
    """Return how the sitemap lists a route registered with the ``sitemap`` option.

    Args:
        rule: The URL rule.
        methods: The route's HTTP methods; ``None`` means ``GET`` only.
        sitemap: The option: ``True`` for a route without variables, or a function
            returning the route's entries in a given language.

    Returns:
        The function listing the route's entries.

    Raises:
        ValueError: If the route does not answer ``GET``, which is what crawlers send, or
            ``sitemap=True`` is given for a route with URL variables, whose values only a
            function can supply.
    """
    if methods is not None and "GET" not in {method.upper() for method in methods}:
        raise ValueError(f"Route {rule!r} does not answer GET, so the sitemap cannot list it.")
    if not callable(sitemap) and "<" in rule:
        raise ValueError(
            f"Route {rule!r} has URL variables, so sitemap=True cannot list it; pass a "
            "function returning its SitemapEntry values in a given language instead."
        )
    return t.cast(SitemapEntries, sitemap) if callable(sitemap) else single_url
