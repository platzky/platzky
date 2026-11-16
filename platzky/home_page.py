"""The page each language's home (``/``) shows, read from the site config on each request.

A language's home shows the route at its ``home_page_path``, or else at the default
language's, in its own language; without either, the blog index. The path is matched
against the routes when ``/`` is requested.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

from flask.typing import ResponseReturnValue, RouteCallable
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.routing import MapAdapter, RequestRedirect

from platzky.db.site_config_repository import SiteConfigRepository
from platzky.language_routing import LANG_CODE_ARG
from platzky.models import LanguageCode


@dataclass(frozen=True)
class HomeTarget:
    """The route a home page path matches: its endpoint and view arguments."""

    endpoint: str
    view_args: Mapping[str, Any]


def home_page_path(
    site_config: SiteConfigRepository,
    language: LanguageCode,
    default_language: LanguageCode,
    blog_prefix: str,
) -> str:
    """Return the path a language's home page shows.

    Args:
        site_config: The site content, read for the paths
        language: The language of the home page
        default_language: The language whose path a language without one shows
        blog_prefix: Prefix of the blog, whose index is shown without either path

    Returns:
        The language's ``home_page_path``, else the default language's, else the blog index.
    """
    return (
        site_config.get_localized_content(language).home_page_path
        or site_config.get_localized_content(default_language).home_page_path
        or f"{blog_prefix.rstrip('/')}/"
    )


def match_home_target(routes: MapAdapter, target_path: str) -> HomeTarget:
    """Match a home page path against the routes.

    A path that redirects within the site, such as ``/blog`` to the route ``/blog/``, is
    followed once. The path is matched on the request host, so a route bound to that host may
    resolve back to the home page.

    Args:
        routes: The application's routes bound to the request
        target_path: Home page path of a language

    Returns:
        The matched route.

    Raises:
        NotFound: If the path matches no route, only a route for other methods, a route that
            redirects twice or to another host, or the home page itself.
    """
    try:
        try:
            endpoint, view_args = routes.match(target_path, method="GET")
        except RequestRedirect as redirect:
            redirect_url = urlsplit(redirect.new_url)
            if redirect_url.netloc != routes.server_name:
                raise NotFound() from redirect
            endpoint, view_args = routes.match(unquote(redirect_url.path), method="GET")
    except HTTPException as error:  # no route, other methods only, or a second redirect
        raise NotFound() from error
    if endpoint == "home_page":
        raise NotFound()
    return HomeTarget(
        endpoint, {name: value for name, value in view_args.items() if name != LANG_CODE_ARG}
    )


def is_home_target(
    routes: MapAdapter,
    target_path: str,
    endpoint: str | None,
    view_args: Mapping[str, Any],
) -> bool:
    """Return whether a request is for the page a home page path shows.

    Args:
        routes: The application's routes bound to the request
        target_path: Home page path of the request's language
        endpoint: Endpoint the request matched
        view_args: View arguments the request matched, without the language

    Returns:
        Whether the path matches the same endpoint with the same view arguments.
    """
    try:
        target = match_home_target(routes, target_path)
    except NotFound:
        return False
    return (target.endpoint, target.view_args) == (endpoint, view_args)


def home_page_target_urls(
    routes: MapAdapter,
    paths: Mapping[LanguageCode, str],
    url_for_language: Callable[..., str],
) -> frozenset[str]:
    """Build the URLs of the pages that home page paths show, each in its language.

    Args:
        routes: The application's routes bound to the request
        paths: Home page path of each language
        url_for_language: Builds an endpoint's URL in a language, as ``Engine.url_for_language``

    Returns:
        The absolute URL of each page in its language; none for a path that matches no route,
        or whose route has no URL in that language.
    """
    urls: set[str] = set()
    for language, path in paths.items():
        try:
            target = match_home_target(routes, path)
            urls.add(
                url_for_language(target.endpoint, language, _external=True, **target.view_args)
            )
        except (NotFound, ValueError):
            continue
    return frozenset(urls)


def home_page_target_response(
    routes: MapAdapter,
    view_functions: Mapping[str, RouteCallable],
    target_path: str,
) -> ResponseReturnValue:
    """Render the route a home page path matches, as the home page.

    Args:
        routes: The application's routes bound to the request
        view_functions: The application's views by endpoint
        target_path: Home page path of the request's language

    Returns:
        The response of the matched view.

    Raises:
        NotFound: If the path matches no route, as ``match_home_target``.
        TypeError: If the matched view is async.
    """
    target = match_home_target(routes, target_path)
    result = view_functions[target.endpoint](**target.view_args)
    if isinstance(result, Awaitable):
        raise TypeError(f"Async view functions are not supported (endpoint: {target.endpoint!r})")
    return result
