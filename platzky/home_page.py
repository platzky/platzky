"""The page each language's home (``/``) shows, read from the site config at startup.

A language's home shows the route at its ``home_page_path``, without a language prefix. The
default language without one shows the blog index; another language without one redirects to
the default language's home.
"""

import logging
from collections.abc import Awaitable, Collection, Iterable, Mapping
from types import MappingProxyType
from urllib.parse import unquote, urlparse

from flask import abort
from flask.typing import ResponseReturnValue, RouteCallable
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import Map, MapAdapter, RequestRedirect

from platzky.language_routing import LANG_CODE_ARG
from platzky.models import LanguageCode

logger = logging.getLogger(__name__)


class HomePagePathError(ValueError):
    """A configured home page path is unusable."""


def home_page_paths_with_default(
    stored: Mapping[LanguageCode, str], default_language: LanguageCode, blog_prefix: str
) -> Mapping[LanguageCode, str]:
    """Return the home page path of each language that has one.

    The default language's home is the blog index unless it has a page set.

    Args:
        stored: Home page path stored for each language, empty when it has none
        default_language: The site's default language
        blog_prefix: URL prefix of the blog

    Returns:
        Languages with a home page of their own, mapped to its path without a language prefix.
    """
    return MappingProxyType(
        {
            **{language: path for language, path in stored.items() if path},
            default_language: stored[default_language] or f"{blog_prefix.rstrip('/')}/",
        }
    )


def resolve_home_page_paths(
    url_map: Map, paths: Mapping[LanguageCode, str], languages: Collection[LanguageCode]
) -> Mapping[LanguageCode, str]:
    """Check the home page paths against the routes and return them as the routes serve them.

    A path its route serves only in another form, such as ``/blog`` for the route ``/blog/``,
    is replaced by that form, with a warning. Paths are matched on the host ``localhost``, so
    routes bound to other hosts are not considered. Whether a path matches a route at all is
    not checked: host applications register their own routes after the app is created.

    Args:
        url_map: The application's routes, all registered
        paths: Home page path of each language that has one
        languages: Every language of the site

    Returns:
        The paths as their routes serve them.

    Raises:
        HomePagePathError: If a path starts with a language code, redirects to a path that
            redirects again, or resolves to the home route itself, which would recurse.
    """
    adapter = url_map.bind("localhost")
    served_paths = {}
    for language, path in paths.items():
        if path.lstrip("/").split("/")[0] in languages:
            raise HomePagePathError(
                f"The home page path {path!r} of language {language} has a language prefix; "
                "write it without one, as the language of the home page is already known."
            )
        served_paths[language] = path
        try:
            endpoint, _ = adapter.match(path, method="GET")
        except RequestRedirect as redirect_to:
            served_paths[language] = unquote(urlparse(redirect_to.new_url).path)
            logger.warning(
                "The home page path %r of language %s is served as %r; write it in that form",
                path,
                language,
                served_paths[language],
            )
            try:
                endpoint, _ = adapter.match(served_paths[language], method="GET")
            except RequestRedirect as error:
                raise HomePagePathError(
                    f"The home page path {path!r} of language {language} redirects to "
                    f"{served_paths[language]!r}, which redirects again; configure the page "
                    "to show instead."
                ) from error
            except (NotFound, MethodNotAllowed):
                continue
        except (NotFound, MethodNotAllowed):
            continue
        if endpoint == "home_page":
            raise HomePagePathError(
                f"The home page path {path!r} of language {language} resolves to the "
                "home page itself; configure the page to show instead."
            )
    return MappingProxyType(served_paths)


def warn_about_languages_without_a_home_page(
    languages: Iterable[LanguageCode], home_page_paths: Mapping[LanguageCode, str]
) -> None:
    """Log a warning for each language whose home redirects, as it has no page of its own."""
    for language in sorted(set(languages) - set(home_page_paths)):
        logger.warning(
            "Language %s has no home_page_path; its home page redirects (302) to the "
            "default language's home page",
            language,
        )


def home_page_target_response(
    routes: MapAdapter,
    view_functions: Mapping[str, RouteCallable],
    target_path: str,
) -> ResponseReturnValue:
    """Render the route a home page path matches, as the home page.

    The path is matched on the request host, unlike at startup, so a route bound to that host
    may resolve back to the home page; that, like a path matching no route, only another
    method's route, or a route only in another form, gives the 404 page.

    Args:
        routes: The application's routes bound to the request
        view_functions: The application's views by endpoint
        target_path: Home page path of the request's language

    Returns:
        The response of the matched view.

    Raises:
        NotFound: If the path matches no route, only a route for other methods or in another
            form, or the home page itself.
        TypeError: If the matched view is async.
    """
    try:
        endpoint, view_args = routes.match(target_path, method="GET")
    except (MethodNotAllowed, RequestRedirect):
        abort(404)
    if endpoint == "home_page":
        abort(404)
    result = view_functions[endpoint](
        **{name: value for name, value in view_args.items() if name != LANG_CODE_ARG}
    )
    if isinstance(result, Awaitable):
        raise TypeError(f"Async view functions are not supported (endpoint: {endpoint!r})")
    return result
