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
    url_for,
)
from werkzeug.routing import BuildError

from platzky.language_routing import (
    LANG_CODE_ARG,
    SiteLanguages,
    language_url,
    served_languages,
)
from platzky.models import LanguageCode
from platzky.sitemap import SitemapEntry, SitemapProvider

logger = logging.getLogger(__name__)


def _is_localized(endpoint: str) -> bool:
    """Return whether an endpoint is also served under a language prefix (``multilang``)."""
    return any(LANG_CODE_ARG in rule.arguments for rule in current_app.url_map.iter_rules(endpoint))


def _endpoint_url(endpoint: str, prefixed_language: LanguageCode | None, **values: object) -> str:
    """Return the absolute URL of an endpoint on the requesting host.

    Args:
        endpoint: The endpoint; for a prefixed language, one registered with ``multilang``.
        prefixed_language: The language whose prefix the URL has, or None for no prefix.
        **values: The endpoint's URL variables, as for ``url_for``.

    Returns:
        The URL, as the routes build it.
    """
    url_values: dict[str, t.Any] = {**values, LANG_CODE_ARG: prefixed_language}
    return url_for(endpoint, _external=True, **url_values)


def _route_entries(
    prefixes: t.Mapping[LanguageCode, str],
    endpoint: str,
    provider: SitemapProvider,
    excluded_prefixes: tuple[str, ...],
) -> list[SitemapEntry]:
    """Return a route's sitemap entries in every language served on the host.

    Args:
        prefixes: Languages served on the current host mapped to their URL prefix.
        endpoint: The route's endpoint.
        provider: Its ``sitemap_provider``.
        excluded_prefixes: Paths to leave out, matched without the language prefix.

    Returns:
        The entries, except those under an excluded path; none, with a warning logged, if one
        of its URLs cannot be built, e.g. a URL variable is missing.
    """
    try:
        return [
            entry
            for lang, prefix in prefixes.items()
            if not prefix or _is_localized(endpoint)
            for entry in provider(lang, partial(_endpoint_url, endpoint, lang if prefix else None))
            if not urllib.parse.urlparse(entry.loc)
            .path.removeprefix(prefix)
            .startswith(excluded_prefixes)
        ]
    except BuildError as error:
        logger.warning("The sitemap leaves out %r, whose URL cannot be built: %s", endpoint, error)
        return []


def create_seo_blueprint(
    config: dict[str, t.Any],
    languages: SiteLanguages,
    sitemap_providers: t.Mapping[str, SitemapProvider],
    home_page_paths: t.Mapping[LanguageCode, str],
) -> Blueprint:
    """Create SEO blueprint with routes for robots.txt and sitemap.xml.

    Args:
        config: Configuration dictionary with SEO settings
        languages: The site's languages; the sitemap lists those served on the requesting
            host
        sitemap_providers: Endpoints registered with the ``sitemap_provider`` option, mapped to
            their entries; read on every sitemap request, so routes registered after the
            blueprint is created are included
        home_page_paths: The home page path of each language with a page of its own, without a
            language prefix; a path is left out of the sitemap, as its canonical URL is the
            home, and so is the home of a language without one, as it redirects

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
        prefixes = served_languages(languages, request.host)
        excluded_prefixes = tuple(config.get("SITEMAP_EXCLUDED_PREFIXES") or [])

        entries = [
            entry
            for endpoint, provider in sitemap_providers.items()
            for entry in _route_entries(prefixes, endpoint, provider, excluded_prefixes)
        ]
        home_urls = {
            language_url(
                languages,
                language,
                request.scheme,
                request.host,
                home_page_paths.get(language, "/"),
            )
            for language in prefixes
        }
        urls = {entry.loc: entry.lastmod for entry in entries if entry.loc not in home_urls}
        xml_sitemap = render_template("sitemap.xml", urls=urls)
        response = make_response(xml_sitemap)
        response.headers["Content-Type"] = "application/xml"
        return response

    return seo
