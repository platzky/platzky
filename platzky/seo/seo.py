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

INTERNAL_NAMESPACES = frozenset({"static", "seo", "admin", "login", "health", "api"})
INTERNAL_PATH_PREFIXES = ("/lang/",)


def _is_public_route(rule: Rule, extra_excluded_prefixes: tuple[str, ...] = ()) -> bool:
    """Return True if the route should be included in the sitemap.

    Args:
        rule: A registered URL rule.
        extra_excluded_prefixes: Further paths to leave out, from ``SITEMAP_EXCLUDED_PREFIXES``.

    Returns:
        Whether crawlers can fetch the route (GET), it stands for a known set of URLs (no view
        arguments besides the language), and it is neither internal nor excluded.
    """
    fetchable = "GET" in (rule.methods or ())
    enumerable = rule.arguments <= {LANG_CODE_ARG}
    internal = rule.endpoint.split(".")[0] in INTERNAL_NAMESPACES
    excluded = str(rule).startswith(INTERNAL_PATH_PREFIXES + extra_excluded_prefixes)
    return fetchable and enumerable and not internal and not excluded


def _route_paths(rule: Rule, prefixes: t.Mapping[str, str]) -> list[str]:
    """Return the paths a public route is served at in the languages of the current host.

    Args:
        rule: A public route
        prefixes: Languages served on the current host mapped to their URL prefix

    Returns:
        The route's path, or one path per prefixed language for a localized route
    """
    values: list[dict[str, t.Any]] = [
        {LANG_CODE_ARG: lang} for lang, prefix in prefixes.items() if prefix
    ]
    localized = LANG_CODE_ARG in rule.arguments
    return [url_for(rule.endpoint, **v) for v in values] if localized else [str(rule)]


def _blog_entries(host_base: str, lang: str, db: DB, blog_prefix: str) -> list[dict[str, str]]:
    """Generate sitemap entries for all blog posts.

    Args:
        host_base: Base URL including any language prefix (e.g. 'https://example.com/uk')
        lang: Language code for posts to include
        db: Database instance for accessing blog posts
        blog_prefix: URL prefix for blog routes

    Returns:
        List of dictionaries with sitemap URL entries (loc, lastmod)
    """
    dynamic_urls = []
    # TODO: Add get_list_of_posts for faster getting just list of it
    for post in db.get_all_posts(lang):
        url: dict[str, str] = {"loc": f"{host_base}{blog_prefix}/{post.slug}"}
        if post.date is not None:
            url["lastmod"] = post.date.date().isoformat()
        dynamic_urls.append(url)
    return dynamic_urls


def create_seo_blueprint(
    db: DB,
    config: dict[str, t.Any],
    languages: SiteLanguages,
) -> Blueprint:
    """Create SEO blueprint with routes for robots.txt and sitemap.xml.

    Args:
        db: Database instance for accessing blog content
        config: Configuration dictionary with SEO and blog settings
        languages: The site's languages; the sitemap lists those served on the requesting
            host

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

        Lists every language served on the requesting host. lastmod and priority tags
        omitted on static pages; lastmod included on dynamic content such as blog posts.

        Returns:
            XML response containing the sitemap
        """
        prefixes = served_languages(languages, request.host)

        host_components = urllib.parse.urlparse(request.host_url)
        host_base = host_components.scheme + "://" + host_components.netloc

        extra_excluded = tuple(config.get("SITEMAP_EXCLUDED_PREFIXES") or [])

        static_urls = [
            {"loc": f"{host_base}{path}"}
            for rule in current_app.url_map.iter_rules()
            if _is_public_route(rule, extra_excluded)
            for path in _route_paths(rule, prefixes)
        ]

        dynamic_urls = [
            entry
            for lang, prefix in prefixes.items()
            for entry in _blog_entries(host_base + prefix, lang, db, config["BLOG_PREFIX"])
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
