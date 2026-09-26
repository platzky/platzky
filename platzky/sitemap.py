"""What a route contributes to ``sitemap.xml``, declared with its ``sitemap`` route option."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SitemapEntry:
    """One URL in the sitemap.

    Attributes:
        loc: The page's absolute URL, e.g. from ``Engine.url_for_language``.
        lastmod: When the page last changed, if known.
    """

    loc: str
    lastmod: date | None = None


SitemapEntries = Callable[[str], Iterable[SitemapEntry]]
"""Returns a route's sitemap entries in the language it is given."""


def check_sitemap_route(rule: str, methods: Iterable[str] | None, sitemap: object) -> None:
    """Reject a route registered with the ``sitemap`` option that the sitemap cannot list.

    Args:
        rule: The URL rule.
        methods: The route's HTTP methods; ``None`` means ``GET`` only.
        sitemap: The option: ``True`` for a route without variables, or a function
            returning the route's entries in a given language.

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
            "function returning its SitemapEntry URLs in a given language instead."
        )
