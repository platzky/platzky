"""The page each language's home (``/``) shows, read from the site config at startup.

A language's home shows the route at its ``home_page_path``, without a language prefix. The
default language without one shows the blog index; another language without one redirects to
the default language's home. The path is matched against the routes when ``/`` is requested.
"""

import logging
from collections.abc import Awaitable, Iterable, Mapping
from types import MappingProxyType
from urllib.parse import unquote, urlsplit

from flask.typing import ResponseReturnValue, RouteCallable
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import MapAdapter, RequestRedirect

from platzky.language_routing import LANG_CODE_ARG
from platzky.models import LanguageCode

logger = logging.getLogger(__name__)


class HomePagePathError(ValueError):
    """A configured home page path is unusable."""


def home_page_paths(
    stored: Mapping[LanguageCode, str], default_language: LanguageCode, blog_prefix: str
) -> Mapping[LanguageCode, str]:
    """Return the home page path of each language that has one.

    The default language's home is the blog index unless it has a page set. Whether a path
    matches a route is not checked: host applications register their own routes after the
    app is created.

    Args:
        stored: Home page path stored for each language of the site, empty when it has none
        default_language: The site's default language
        blog_prefix: URL prefix of the blog

    Returns:
        Languages with a home page of their own, mapped to its path without a language prefix.

    Raises:
        HomePagePathError: If a path is ``/`` (the home page itself) or starts with a language
            code of the site.
    """
    paths = {
        **{language: path for language, path in stored.items() if path},
        default_language: stored[default_language] or f"{blog_prefix.rstrip('/')}/",
    }
    for language, path in paths.items():
        if not path.strip("/"):
            raise HomePagePathError(
                f"The home page path {path!r} of language {language} is the home page itself; "
                "configure the page to show instead."
            )
        if path.lstrip("/").split("/")[0] in stored:
            raise HomePagePathError(
                f"The home page path {path!r} of language {language} has a language prefix; "
                "write it without one, as the language of the home page is already known."
            )
    return MappingProxyType(paths)


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

    A path its route serves only in another form, such as ``/blog`` for the route ``/blog/``,
    is followed to that form once. The path is matched on the request host, so a route bound
    to that host may resolve back to the home page.

    Args:
        routes: The application's routes bound to the request
        view_functions: The application's views by endpoint
        target_path: Home page path of the request's language

    Returns:
        The response of the matched view.

    Raises:
        NotFound: If the path matches no route, only a route for other methods, a route that
            redirects twice, or the home page itself.
        TypeError: If the matched view is async.
    """
    try:
        try:
            endpoint, view_args = routes.match(target_path, method="GET")
        except RequestRedirect as redirect:
            endpoint, view_args = routes.match(
                unquote(urlsplit(redirect.new_url).path), method="GET"
            )
    except (MethodNotAllowed, NotFound, RequestRedirect) as error:
        raise NotFound() from error
    if endpoint == "home_page":
        raise NotFound()
    result = view_functions[endpoint](
        **{name: value for name, value in view_args.items() if name != LANG_CODE_ARG}
    )
    if isinstance(result, Awaitable):
        raise TypeError(f"Async view functions are not supported (endpoint: {endpoint!r})")
    return result
