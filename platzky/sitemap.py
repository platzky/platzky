"""What a route contributes to ``sitemap.xml``, declared with its ``sitemap_entries`` option."""

import logging
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

logger = logging.getLogger(__name__)


def single_url(_lang: str, url: UrlFor) -> list[SitemapEntry]:
    """List the one URL of a route without URL variables."""
    return [SitemapEntry(url())]


def is_route_allowed_in_sitemap(
    rule: str, methods: Iterable[str] | None, sitemap_entries: SitemapEntries
) -> bool:
    """Return whether a route registered with ``sitemap_entries`` can be listed.

    A route that cannot is logged as a warning, so the site still starts without it.

    Args:
        rule: The URL rule.
        methods: The route's HTTP methods; ``None`` means ``GET`` only.
        sitemap_entries: The function listing the route's entries.

    Returns:
        Whether the route answers ``GET``, which is what crawlers send, and its entries
        function can build its URLs: the route has no URL variables, or the function fills
        them in, which ``single_url`` cannot.
    """
    answers_get = methods is None or "GET" in {method.upper() for method in methods}
    fills_its_variables = sitemap_entries is not single_url
    has_no_variables = "<" not in rule
    if not answers_get:
        logger.warning("Route %r does not answer GET, so the sitemap leaves it out.", rule)
    if not (fills_its_variables or has_no_variables):
        logger.warning(
            "Route %r has URL variables, which single_url cannot fill, so the sitemap leaves "
            "it out; pass a function that lists its URLs instead.",
            rule,
        )
    return answers_get and (fills_its_variables or has_no_variables)
