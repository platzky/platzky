"""Which URLs a shortcode may emit, and why one was refused.

Public because rendering is not the only place the question comes up: an application
holding a stored value renders it through ``Shortcode.render_value`` and has to decide
what to show when the shortcode declines it. Asking here is what keeps that decision on
the same policy as the rendering, rather than growing a second allowlist that drifts.
"""

from __future__ import annotations

from urllib.parse import urlparse

#: Schemes for a URL something is *fetched* from and embedded — an image source. Only the
#: two that fetch a document over the network: an ``<img src="mailto:…">`` is not an image.
EMBED_SCHEMES = frozenset({"http", "https"})

#: Schemes for a URL a reader *navigates* to. The embeddable two, plus the two that hand
#: off to another application rather than fetching anything — a phone number and an email
#: address are ordinary things to publish, and on a phone they are the useful form of a
#: contact detail.
LINK_SCHEMES = frozenset({"http", "https", "mailto", "tel"})


def _phrase(schemes: frozenset[str]) -> str:
    """Render a scheme set as prose for the tail of a rejection message.

    Args:
        schemes: The permitted schemes.

    Returns:
        Them, sorted, joined as "a, b or c".
    """
    names = sorted(schemes)
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} or {names[-1]}"


def is_url_allowed(url: str, *, schemes: frozenset[str] = EMBED_SCHEMES) -> bool:
    """Report whether a URL is one a shortcode may emit.

    Allowed: the given ``schemes``, and paths rooted at ``/``. Everything else is
    refused — an empty URL, because a link or image with no destination has nothing to
    point at; any other scheme, which is what keeps ``javascript:`` and ``data:`` out; a
    bare relative path such as ``photo.jpg``, which resolves against whichever page is
    showing the content and so means one thing in a post and another in a listing; and a
    protocol-relative ``//host/path``, which carries no scheme but is external anyway.

    Args:
        url: The URL as written in the shortcode.
        schemes: The schemes permitted here. Defaults to ``EMBED_SCHEMES``, the stricter
            of the two, so a caller that has not thought about it gets the narrow answer.

    Returns:
        True if a shortcode may use it.
    """
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme:
        return parsed.scheme in schemes
    if parsed.netloc:
        return False
    return url.startswith("/")


def rejection_reason(url: str, *, schemes: frozenset[str] = EMBED_SCHEMES) -> str:
    """Say why ``is_url_allowed`` refused this URL, without quoting the URL itself.

    A rejected value is the one place a URL is most likely to be malformed or private —
    credentials in a ``ftp://user:pass@host``, a signed query, a ``data:`` payload — and a
    log line is the wrong place for any of it. The scheme is the exception: it is what was
    wrong, it is a fixed vocabulary, and it carries nothing the author typed beyond it.

    Args:
        url: The URL as written in the shortcode.
        schemes: The schemes that were permitted, named in the message so the reason says
            what would have worked. Must match what ``is_url_allowed`` was asked.

    Returns:
        A phrase naming the fault, safe to log verbatim.
    """
    if not url:
        return "no url was given"
    parsed = urlparse(url)
    if parsed.scheme:
        return f"scheme {parsed.scheme!r} is not allowed; use {_phrase(schemes)}"
    if parsed.netloc:
        return "a protocol-relative '//host/path' url has no scheme; write http(s) instead"
    return "a relative path resolves against whichever page shows it; start it with '/'"
