"""Flask blueprint for SEO functionality including robots.txt and sitemap.xml."""

import typing as t
import urllib.parse
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

from platzky.language_routing import LANG_CODE_ARG, SiteLanguages, served_languages
from platzky.sitemap import SitemapEntries, SitemapEntry


def _is_localized(endpoint: str) -> bool:
    """Return whether an endpoint is also served under a language prefix (``multilang``)."""
    return any(LANG_CODE_ARG in rule.arguments for rule in current_app.url_map.iter_rules(endpoint))


def _entry_path(endpoint: str, entry: SitemapEntry, lang_code: str | None) -> str:
    """Return the path of a sitemap entry, under ``lang_code``'s prefix unless it is None."""
    values: dict[str, t.Any] = {**entry.values, LANG_CODE_ARG: lang_code}
    return url_for(endpoint, **values)


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
        sitemap_entries: Endpoints registered with the ``sitemap`` route option, mapped to
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

        Lists the URLs of every route registered with the ``sitemap`` option, in every
        language served on the requesting host, with their lastmod when known.

        Returns:
            XML response containing the sitemap
        """
        prefixes = served_languages(languages, request.host)
        host_components = urllib.parse.urlparse(request.host_url)
        host_base = host_components.scheme + "://" + host_components.netloc
        excluded_prefixes = tuple(config.get("SITEMAP_EXCLUDED_PREFIXES") or [])

        listed = [
            (_entry_path(endpoint, entry, lang if prefix else None), entry.lastmod)
            for endpoint, list_entries in sitemap_entries.items()
            for lang, prefix in prefixes.items()
            if not prefix or _is_localized(endpoint)
            for entry in list_entries(lang)
        ]
        urls = {
            f"{host_base}{path}": lastmod
            for path, lastmod in listed
            if not path.startswith(excluded_prefixes)
        }
        xml_sitemap = render_template("sitemap.xml", urls=urls)
        response = make_response(xml_sitemap)
        response.headers["Content-Type"] = "application/xml"
        return response

    return seo
