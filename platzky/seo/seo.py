"""Flask blueprint for SEO functionality including robots.txt and sitemap.xml."""

import logging
import typing as t
import urllib.parse
from functools import partial
from os.path import dirname

from flask import (
    Blueprint,
    Response,
    current_app,
    make_response,
    render_template,
    request,
)
from werkzeug.routing import BuildError

from platzky.language_routing import LANG_CODE_ARG, LanguageRouting
from platzky.models import LanguageCode
from platzky.sitemap import SitemapEntry, SitemapProvider

logger = logging.getLogger(__name__)


def _is_localized(endpoint: str) -> bool:
    """Return whether an endpoint is also served under a language prefix (``multilang``)."""
    return any(LANG_CODE_ARG in rule.arguments for rule in current_app.url_map.iter_rules(endpoint))


def _is_excluded(loc: str, prefix: str, excluded_prefixes: tuple[str, ...]) -> bool:
    """Return whether a URL's path, without its language prefix, is under an excluded path."""
    return urllib.parse.urlparse(loc).path.removeprefix(prefix).startswith(excluded_prefixes)


def _route_entries(
    routing: LanguageRouting,
    languages_served: t.Sequence[LanguageCode],
    endpoint: str,
    provider: SitemapProvider,
    url_for_language: t.Callable[..., str],
    excluded_prefixes: tuple[str, ...],
) -> list[SitemapEntry]:
    """Return a route's sitemap entries in every language served on the host.

    Args:
        routing: How the site's languages map to hosts and URL prefixes.
        languages_served: Languages served on the current host.
        endpoint: The route's endpoint.
        provider: Its ``sitemap_provider``.
        url_for_language: Builds an endpoint's URL in a language, as ``Engine.url_for_language``.
        excluded_prefixes: Paths to leave out, matched without the language prefix.

    Returns:
        The entries, except those under an excluded path; none, with a warning logged, if one
        of its URLs cannot be built, e.g. a URL variable is missing.
    """
    entries: list[SitemapEntry] = []
    try:
        entries = [
            entry
            for lang in languages_served
            if not routing.url_prefix(lang) or _is_localized(endpoint)
            for entry in provider(lang, partial(url_for_language, endpoint, lang, _external=True))
            if not _is_excluded(entry.loc, routing.url_prefix(lang), excluded_prefixes)
        ]
    except BuildError as error:
        logger.warning("The sitemap leaves out %r, whose URL cannot be built: %s", endpoint, error)
    return entries


def create_seo_blueprint(
    config: dict[str, t.Any],
    routing: LanguageRouting,
    sitemap_providers: t.Mapping[str, SitemapProvider],
    url_for_language: t.Callable[..., str],
) -> Blueprint:
    """Create SEO blueprint with routes for robots.txt and sitemap.xml.

    Args:
        config: Configuration dictionary with SEO settings
        routing: How the site's languages map to hosts; the sitemap lists those served on the
            requesting host
        sitemap_providers: Endpoints registered with the ``sitemap_provider`` option, mapped to
            their entries; read on every sitemap request, so routes registered after the
            blueprint is created are included
        url_for_language: Builds an endpoint's URL in a language, as ``Engine.url_for_language``

    Returns:
        Configured Flask Blueprint for SEO functionality
    """
    seo = Blueprint(
        "seo",
        __name__,
        url_prefix=config["SEO_PREFIX"],
        template_folder=f"{dirname(__file__)}/../templates",
    )

    @seo.route("/robots.txt")
    def robots() -> Response:
        """Generate robots.txt file for search engine crawlers.

        Returns:
            Text response containing robots.txt directives
        """
        robots_response = render_template("robots.txt", domain=request.host, mimetype="text/plain")
        response = make_response(robots_response)
        response.headers["Content-Type"] = "text/plain"
        return response

    @seo.route("/sitemap.xml")  # TODO: Try to replace sitemap logic with flask-sitemap module
    def sitemap() -> Response:
        """Route to dynamically generate a sitemap of your website/application.

        Lists the URLs of every route registered with the ``sitemap_provider`` option, in every
        language served on the requesting host, with their lastmod when known.

        Returns:
            XML response containing the sitemap
        """
        languages_served = routing.get_languages_on_host(request.host)
        excluded_prefixes = tuple(config.get("SITEMAP_EXCLUDED_PREFIXES") or [])

        entries = [
            entry
            for endpoint, provider in sitemap_providers.items()
            for entry in _route_entries(
                routing, languages_served, endpoint, provider, url_for_language, excluded_prefixes
            )
        ]
        urls = {entry.loc: entry.lastmod for entry in entries}
        xml_sitemap = render_template("sitemap.xml", urls=urls)
        response = make_response(xml_sitemap)
        response.headers["Content-Type"] = "application/xml"
        return response

    return seo
