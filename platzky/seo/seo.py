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
from werkzeug.routing import Rule

from platzky.db.db import DB
from platzky.language_routing import LANG_CODE_ARG, SiteLanguages, served_languages
from platzky.models import Post


def _route_paths(rule: Rule, prefixes: t.Mapping[str, str]) -> list[str]:
    """Return the paths a sitemap route is served at in the languages of the current host.

    Args:
        rule: A route registered with ``sitemap=True``
        prefixes: Languages served on the current host mapped to their URL prefix

    Returns:
        The route's path, or one path per prefixed language for a localized route
    """
    values: list[dict[str, t.Any]] = [
        {LANG_CODE_ARG: lang} for lang, prefix in prefixes.items() if prefix
    ]
    localized = LANG_CODE_ARG in rule.arguments
    return [url_for(rule.endpoint, **v) for v in values] if localized else [str(rule)]


def _content_entries(base_url: str, contents: t.Iterable[Post]) -> list[dict[str, str]]:
    """Return sitemap entries for posts or pages published under a base URL.

    Args:
        base_url: URL their slugs are appended to (e.g. 'https://example.com/pl/blog')
        contents: The posts or pages

    Returns:
        One entry per item: its URL (loc), plus its date (lastmod) when it has one
    """
    return [
        {
            "loc": f"{base_url}/{content.slug}",
            **({"lastmod": content.date.date().isoformat()} if content.date else {}),
        }
        for content in contents
    ]


def create_seo_blueprint(
    db: DB,
    config: dict[str, t.Any],
    languages: SiteLanguages,
    sitemap_endpoints: t.Collection[str],
) -> Blueprint:
    """Create SEO blueprint with routes for robots.txt and sitemap.xml.

    Args:
        db: Database instance for accessing blog content
        config: Configuration dictionary with SEO and blog settings
        languages: The site's languages; the sitemap lists those served on the requesting
            host
        sitemap_endpoints: Endpoints registered with ``sitemap=True``; read on every sitemap
            request, so routes registered after the blueprint is created are included

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

        Lists the routes registered with ``sitemap=True``, and the blog's posts and pages,
        in every language served on the requesting host. lastmod is given for posts and pages
        that have a date.

        Returns:
            XML response containing the sitemap
        """
        prefixes = served_languages(languages, request.host)

        host_components = urllib.parse.urlparse(request.host_url)
        host_base = host_components.scheme + "://" + host_components.netloc

        excluded_prefixes = tuple(config.get("SITEMAP_EXCLUDED_PREFIXES") or [])

        static_urls = [
            {"loc": f"{host_base}{path}"}
            for rule in current_app.url_map.iter_rules()
            if rule.endpoint in sitemap_endpoints and not str(rule).startswith(excluded_prefixes)
            for path in _route_paths(rule, prefixes)
        ]

        blog_prefix = config["BLOG_PREFIX"]
        dynamic_urls = [
            entry
            for lang, prefix in prefixes.items()
            for entry in [
                *_content_entries(f"{host_base}{prefix}{blog_prefix}", db.get_all_posts(lang)),
                *_content_entries(f"{host_base}{prefix}{blog_prefix}/page", db.get_all_pages(lang)),
            ]
        ]

        statics = list({v["loc"]: v for v in static_urls}.values())
        dynamics = list({v["loc"]: v for v in dynamic_urls}.values())
        xml_sitemap = render_template(
            "sitemap.xml",
            static_urls=statics,
            dynamic_urls=dynamics,
            host_base=host_base,
        )
        response = make_response(xml_sitemap)
        response.headers["Content-Type"] = "application/xml"
        return response

    return seo
