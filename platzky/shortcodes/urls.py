"""Which URLs may be emitted where, and why one was refused.

Public because rendering is not the only place the question comes up: an application
holding a stored value renders it through ``Shortcode.render_value`` and has to decide what
to show when the shortcode declines it. Asking here is what keeps that decision on the same
policy as the rendering, rather than growing a second allowlist that drifts.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class UrlPolicy:
    """The URLs allowed in one position, and the reason for turning one away.

    A position — a link's destination, an image's source — is one policy object rather than
    a scheme set passed at each call. Passing the set made every caller state it twice, to
    ask whether a URL was allowed and again to say why it was not, with nothing to keep the
    two in step; a message naming the wrong schemes is exactly the kind of wrong a log line
    never gets caught being. Here the question is asked once, of a value that already knows
    what it permits.
    """

    #: The URL schemes this position permits. A rooted path is always allowed as well.
    schemes: frozenset[str]

    def rejection(self, url: str) -> str | None:
        """Say why this URL may not be used here, or ``None`` if it may.

        The reason never quotes the URL itself. A rejected value is the one place a URL is
        most likely to be malformed or private — credentials in an ``ftp://user:pass@host``,
        a signed query, a ``data:`` payload — and a log line is the wrong place for any of
        it. The scheme is the exception: it is what was wrong, it is a fixed vocabulary, and
        it carries nothing the author typed beyond it.

        Refused are an empty URL, because a link or image with no destination has nothing to
        point at; any scheme outside ``schemes``, which is what keeps ``javascript:`` and
        ``data:`` out; a bare relative path such as ``photo.jpg``, which resolves against
        whichever page is showing the content and so means one thing in a post and another
        in a listing; and a protocol-relative ``//host/path``, which carries no scheme but
        is external anyway.

        Args:
            url: The URL as written.

        Returns:
            A phrase naming the fault, safe to log verbatim, or ``None`` if the URL is fine.
        """
        if not url:
            return "no url was given"
        parsed = urlparse(url)
        if parsed.scheme:
            if parsed.scheme in self.schemes:
                return None
            return f"scheme {parsed.scheme!r} is not allowed; use {self._permitted()}"
        if parsed.netloc:
            return "a protocol-relative '//host/path' url has no scheme; write http(s) instead"
        if url.startswith("/"):
            return None
        return "a relative path resolves against whichever page shows it; start it with '/'"

    def allows(self, url: str) -> bool:
        """Report whether this URL may be used here.

        For a caller with nothing to log. Defined in terms of ``rejection`` so the two can
        never disagree about a URL.

        Args:
            url: The URL as written.

        Returns:
            True if the URL may be used.
        """
        return self.rejection(url) is None

    def _permitted(self) -> str:
        """Render the permitted schemes as prose for the tail of a rejection message.

        Returns:
            Them, sorted, joined as "a, b or c".
        """
        names = sorted(self.schemes)
        if len(names) == 1:
            return names[0]
        return f"{', '.join(names[:-1])} or {names[-1]}"


#: For a URL a reader *navigates* to. The two that fetch a document, plus the two that hand
#: off to another application rather than fetching anything — a phone number and an email
#: address are ordinary things to publish, and on a phone they are the useful form of a
#: contact detail.
LINK_URLS = UrlPolicy(frozenset({"http", "https", "mailto", "tel"}))

#: For a URL something is *fetched* from and embedded, such as an image source. Only the two
#: that fetch a document over the network: an ``<img src="mailto:…">`` is not an image.
EMBED_URLS = UrlPolicy(frozenset({"http", "https"}))
