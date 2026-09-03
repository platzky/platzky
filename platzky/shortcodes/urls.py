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
    never gets caught being. Asking a value that already knows what it permits is what
    removes the chance to disagree with itself.
    """

    #: The URL schemes this position permits, lowercased. A rooted path is always allowed
    #: as well. May be empty, for a position that permits nothing but a rooted path.
    schemes: frozenset[str]

    def __post_init__(self) -> None:
        """Lowercase the declared schemes, because that is what they will be compared against.

        ``urlparse`` lowercases the scheme it parses, so a policy declared ``{"HTTPS"}`` would
        otherwise match nothing at all and explain itself with "scheme 'https' is not allowed;
        use HTTPS" — failing closed, which is the safe direction, but silently and with advice
        that contradicts itself. Normalising here means a caller cannot declare a policy that
        refuses the very scheme it names.
        """
        lowered = frozenset(scheme.lower() for scheme in self.schemes)
        if lowered != self.schemes:
            # The dataclass is frozen, so this is the sanctioned way to normalise in place.
            object.__setattr__(self, "schemes", lowered)

    def allows(self, url: str) -> bool:
        """Report whether this URL may be used here.

        The question a caller asks first. ``rejection_reason`` answers the follow-up, and is
        defined below as the thing this one is derived from, so the two can never disagree
        about a URL — which was the whole fault with passing a scheme set to each of a
        separate pair of functions.

        Args:
            url: The URL as written.

        Returns:
            True if the URL may be used.
        """
        return self.rejection_reason(url) is None

    def rejection_reason(self, url: str) -> str | None:
        """Say why this URL may not be used here, or ``None`` if it may.

        For the caller that has already been told no by ``allows`` and has somewhere to
        report it. Returning ``None`` for a permitted URL is what lets ``allows`` be one
        line rather than a second copy of the rules.

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
        is external anyway — along with the backslash spellings of it, which reach a host
        just the same in a browser.

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
        # Two leading slashes mean an authority rather than a path — and a browser reads a
        # backslash as a slash for special schemes (WHATWG URL takes `/\`, `\/` and `\\` into
        # the same authority states as `//`), so `/\evil.example/x` fetches from that host
        # while `urlparse` reports an innocent rooted path with no netloc. Checking the two
        # characters directly is what closes that gap; `parsed.netloc` alone does not.
        if parsed.netloc or (len(url) > 1 and url[0] in "/\\" and url[1] in "/\\"):
            return (
                "a protocol-relative '//host/path' url has no scheme; "
                f"use {self._permitted()} instead"
            )
        if url.startswith("/"):
            return None
        return "a relative path resolves against whichever page shows it; start it with '/'"

    def _permitted(self) -> str:
        """Render what this policy accepts, as prose for the tail of a rejection message.

        Total by construction: ``allows`` is defined in terms of ``rejection_reason``, so a
        policy this could not describe would raise out of the *allow check* and fail a whole
        page render rather than refusing one URL. An empty scheme set is a real policy —
        rooted paths only — not a mistake to crash on.

        Returns:
            The schemes, sorted, joined as "a, b or c"; or a description of the rooted-path
            case when there are none.
        """
        names = sorted(self.schemes)
        if not names:
            return "a path starting with '/'"
        if len(names) == 1:
            return names[0]
        return f"{', '.join(names[:-1])} or {names[-1]}"


#: For a URL a reader *navigates* to. The two that fetch a document, plus the two that hand
#: off to another application rather than fetching anything — a phone number and an email
#: address are ordinary things to publish, and on a phone they are the useful form of a
#: contact detail.
LINK_URL_POLICY = UrlPolicy(frozenset({"http", "https", "mailto", "tel"}))
