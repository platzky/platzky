"""Flask blueprint for SEO functionality including robots.txt and sitemap.xml."""

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

from platzky.language_routing import (
    LANG_CODE_ARG,
    SiteLanguages,
    language_url,
    served_languages,
)
from platzky.sitemap import SitemapEntries


def _is_localized(endpoint: str) -> bool:
    """Return whether an endpoint is also served under a language prefix (``multilang``)."""
    return any(LANG_CODE_ARG in rule.arguments for rule in current_app.url_map.iter_rules(endpoint))


def _url_in_language(
    languages: SiteLanguages, endpoint: str, lang_code: str, **values: object
) -> str:
    """Return the absolute URL of an endpoint in a language, on the host that serves it.

    Args:
        languages: The site's languages.
        endpoint: The endpoint; for a domainless language, one registered with ``multilang``.
        lang_code: The language to link to.
        **values: The endpoint's URL variables, as for ``url_for``.

    Returns:
        The URL under the language's prefix, on its own domain or the main host.
    """
    url_values: dict[str, t.Any] = {**values, LANG_CODE_ARG: None}
    path = url_for(endpoint, **url_values)
    return language_url(languages, lang_code, request.scheme, request.host, path)


def create_seo_blueprint(
    config: dict[str, t.Any],
    languages: SiteLanguages,
    sitemap_entries: t.Mapping[str, SitemapEntries],
) -> Blueprint:
    """Create SEO blueprint with routes for robots.txt and sitemap.xml.

    Args:
        config: Configuration dictionary with SEO settings
        languages: The site's languages; the sitemap lists those served on the requesting
            host
        sitemap_entries: Endpoints registered with the ``sitemap_entries`` option, mapped to
            their entries; read on every sitemap request, so routes registered after the
            blueprint is created are included

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

        Lists the URLs of every route registered with the ``sitemap_entries`` option, in every
        language served on the requesting host, with their lastmod when known.

        Returns:
            XML response containing the sitemap
        """
        prefixes = served_languages(languages, request.host)
        excluded_prefixes = tuple(config.get("SITEMAP_EXCLUDED_PREFIXES") or [])

        entries = [
            entry
            for endpoint, list_entries in sitemap_entries.items()
            for lang, prefix in prefixes.items()
            if not prefix or _is_localized(endpoint)
            for entry in list_entries(lang, partial(_url_in_language, languages, endpoint, lang))
        ]
        urls = {
            entry.loc: entry.lastmod
            for entry in entries
            if not urllib.parse.urlparse(entry.loc).path.startswith(excluded_prefixes)
        }
        xml_sitemap = render_template("sitemap.xml", urls=urls)
        response = make_response(xml_sitemap)
        response.headers["Content-Type"] = "application/xml"
        return response

    return seo
