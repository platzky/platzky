"""The page each language's home (``/``) shows, read from the site config on each request.

A language's home shows the route at its ``home_page_path``. The default language without
one shows the blog index; another language without one redirects to the default language's
home. The path is matched against the routes when ``/`` is requested.
"""

from collections.abc import Awaitable, Mapping
from urllib.parse import unquote, urlsplit

from flask.typing import ResponseReturnValue, RouteCallable
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.routing import MapAdapter, RequestRedirect

from platzky.language_routing import LANG_CODE_ARG


def home_page_target_response(
    routes: MapAdapter,
    view_functions: Mapping[str, RouteCallable],
    target_path: str,
) -> ResponseReturnValue:
    """Render the route a home page path matches, as the home page.

    A path that redirects within the site, such as ``/blog`` to the route ``/blog/``, is
    followed once. The path is matched on the request host, so a route bound to that host may
    resolve back to the home page.

    Args:
        routes: The application's routes bound to the request
        view_functions: The application's views by endpoint
        target_path: Home page path of the request's language

    Returns:
        The response of the matched view.

    Raises:
        NotFound: If the path matches no route, only a route for other methods, a route that
            redirects twice or to another host, or the home page itself.
        TypeError: If the matched view is async.
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
    result = view_functions[endpoint](
        **{name: value for name, value in view_args.items() if name != LANG_CODE_ARG}
    )
    if isinstance(result, Awaitable):
        raise TypeError(f"Async view functions are not supported (endpoint: {endpoint!r})")
    return result
