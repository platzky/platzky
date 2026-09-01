from __future__ import annotations

from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


def is_url_allowed(url: str) -> bool:
    """Report whether a URL is one a shortcode may emit.

    Allowed: ``http`` and ``https``, and paths rooted at ``/``. Everything else is
    refused — an empty URL, because a link or image with no destination has nothing to
    point at; any other scheme, which is what keeps ``javascript:`` and ``data:`` out; a
    bare relative path such as ``photo.jpg``, which resolves against whichever page is
    showing the content and so means one thing in a post and another in a listing; and a
    protocol-relative ``//host/path``, which carries no scheme but is external anyway.

    Args:
        url: The URL as written in the shortcode.

    Returns:
        True if a shortcode may use it.
    """
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme:
        return parsed.scheme in _ALLOWED_SCHEMES
    if parsed.netloc:
        return False
    return url.startswith("/")


#: How much of a URL to put in a log line. A shortcode attribute can be 2 KB, and a
#: rejected one is often junk; enough to recognise it is enough to act on.
URL_LOG_LIMIT = 120
