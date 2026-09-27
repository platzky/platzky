"""What a route contributes to ``sitemap.xml``, declared with its ``sitemap_entries`` option."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SitemapEntry:
    """One URL in the sitemap.

    Attributes:
        loc: The page's absolute URL, from the ``url`` its entries function is given.
        lastmod: When the page last changed, if known.
    """

    loc: str
    lastmod: date | None = None


UrlFor = Callable[..., str]
"""Takes a route's URL variables as keywords; returns its absolute URL in one language."""

SitemapEntries = Callable[[str, UrlFor], Iterable[SitemapEntry]]
"""Takes a language code and ``url`` for the route in it; returns the route's entries."""


def single_url(_lang: str, url: UrlFor) -> list[SitemapEntry]:
    """List the one URL of a route without URL variables."""
    return [SitemapEntry(url())]
