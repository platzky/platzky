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


def rejection_reason(url: str) -> str:
    """Say why ``is_url_allowed`` refused this URL, without quoting the URL itself.

    A rejected value is the one place a URL is most likely to be malformed or private —
    credentials in a ``ftp://user:pass@host``, a signed query, a ``data:`` payload — and a
    log line is the wrong place for any of it. The scheme is the exception: it is what was
    wrong, it is a fixed vocabulary, and it carries nothing the author typed beyond it.

    Args:
        url: The URL as written in the shortcode.

    Returns:
        A phrase naming the fault, safe to log verbatim.
    """
    if not url:
        return "no url was given"
    parsed = urlparse(url)
    if parsed.scheme:
        return f"scheme {parsed.scheme!r} is not allowed; use http or https"
    if parsed.netloc:
        return "a protocol-relative '//host/path' url has no scheme; write http(s) instead"
    return "a relative path resolves against whichever page shows it; start it with '/'"
