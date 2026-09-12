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
from platzky.language_routing import LANG_CODE_ARG

INTERNAL_NAMESPACES = frozenset({"static", "seo", "admin", "login", "health", "api"})
INTERNAL_PATH_PREFIXES = ("/lang/",)


def _is_public_route(rule: Rule, extra_excluded_prefixes: tuple[str, ...] = ()) -> bool:
    """Return True if the route should be included in the sitemap."""
    if not rule.methods or "GET" not in rule.methods or rule.arguments - {LANG_CODE_ARG}:
        return False
    namespace = rule.endpoint.split(".")[0]
    if namespace in INTERNAL_NAMESPACES:
        return False
    path = str(rule)
    return not any(path.startswith(p) for p in INTERNAL_PATH_PREFIXES + extra_excluded_prefixes)


def create_seo_blueprint(
    db: DB,
    config: dict[str, t.Any],
    language_prefixes: t.Callable[[], t.Mapping[str, str]],
) -> Blueprint:
    """Create SEO blueprint with routes for robots.txt and sitemap.xml.

    Args:
        db: Database instance for accessing blog content
        config: Configuration dictionary with SEO and blog settings
        language_prefixes: Returns the languages served on the current host, mapped to their
            URL prefix ("" or "/<code>")

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

    def get_blog_entries(
        host_base: str, lang: str, db: DB, blog_prefix: str
    ) -> list[dict[str, str]]:
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
            slug = post.slug
            url: dict[str, str] = {"loc": f"{host_base}{blog_prefix}/{slug}"}
            if post.date is not None:
                url["lastmod"] = post.date.date().isoformat()
            dynamic_urls.append(url)
        return dynamic_urls

    @seo.route("/sitemap.xml")  # TODO: Try to replace sitemap logic with flask-sitemap module
    def sitemap() -> Response:
        """Route to dynamically generate a sitemap of your website/application.

        Lists every language served on the requesting host. lastmod and priority tags
        omitted on static pages; lastmod included on dynamic content such as blog posts.

        Returns:
            XML response containing the sitemap
        """
        prefixes = language_prefixes()

        host_components = urllib.parse.urlparse(request.host_url)
        host_base = host_components.scheme + "://" + host_components.netloc

        extra_excluded = tuple(config.get("SITEMAP_EXCLUDED_PREFIXES") or [])

        # Static routes with static content
        static_urls: list[dict[str, str]] = []
        for rule in current_app.url_map.iter_rules():
            if not _is_public_route(rule, extra_excluded):
                continue
            if LANG_CODE_ARG not in rule.arguments:
                static_urls.append({"loc": f"{host_base}{rule!s}"})
                continue
            for lang, prefix in prefixes.items():
                if prefix:
                    values: dict[str, t.Any] = {LANG_CODE_ARG: lang}
                    static_urls.append({"loc": f"{host_base}{url_for(rule.endpoint, **values)}"})

        dynamic_urls = [
            entry
            for lang, prefix in prefixes.items()
            for entry in get_blog_entries(host_base + prefix, lang, db, config["BLOG_PREFIX"])
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
