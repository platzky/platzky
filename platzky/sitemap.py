"""What a route contributes to ``sitemap.xml``, declared with its ``sitemap`` route option."""

import logging
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

logger = logging.getLogger(__name__)


def is_route_allowed_in_sitemap(rule: str, methods: Iterable[str] | None, sitemap: object) -> bool:
    """Return whether a route registered with the ``sitemap`` option can be listed.

    A route that cannot is logged as a warning, so the site still starts without it.

    Args:
        rule: The URL rule.
        methods: The route's HTTP methods; ``None`` means ``GET`` only.
        sitemap: The option: ``True`` for a route without variables, or a function
            returning the route's entries in a given language.

    Returns:
        Whether the route answers ``GET``, which is what crawlers send, and has its URLs
        supplied: it has no URL variables, or ``sitemap`` is a function listing them.
    """
    answers_get = methods is None or "GET" in {method.upper() for method in methods}
    has_its_urls = callable(sitemap) or "<" not in rule
    if not answers_get:
        logger.warning("Route %r does not answer GET, so the sitemap leaves it out.", rule)
    if not has_its_urls:
        logger.warning(
            "Route %r has URL variables, so sitemap=True cannot list it and the sitemap "
            "leaves it out; pass a function returning its SitemapEntry URLs instead.",
            rule,
        )
    return answers_get and has_its_urls
