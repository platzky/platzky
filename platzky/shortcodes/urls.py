"""Which URLs may be emitted where, and why one was refused."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class UrlPolicy:
    """The URLs allowed in one position — a link's destination, an image's source."""

    #: The schemes this position permits, lowercased. A rooted path is always allowed as
    #: well, and the set may be empty for a position allowing nothing else.
    schemes: frozenset[str]

    def __post_init__(self) -> None:
        """Lowercase the declared schemes, since ``urlparse`` lowercases what it parses."""
        lowered = frozenset(scheme.lower() for scheme in self.schemes)
        if lowered != self.schemes:
            object.__setattr__(self, "schemes", lowered)  # frozen dataclass

    def allows(self, url: str) -> bool:
        """Report whether this URL may be used here.

        Args:
            url: The URL as written.

        Returns:
            True if the URL may be used.
        """
        return self.rejection_reason(url) is None

    def rejection_reason(self, url: str) -> str | None:
        """Say why this URL may not be used here, or ``None`` if it may.

        Refused: an empty URL; any scheme outside ``schemes``, which is what keeps
        ``javascript:`` and ``data:`` out; a bare relative path such as ``photo.jpg``, which
        would resolve against whichever page shows it; and a protocol-relative ``//host/path``
        along with its backslash spellings.

        The reason never quotes the URL back, since a rejected one is the most likely to
        carry credentials or a signed query. The scheme is the exception.

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
        # A browser reads `\` as `/` for special schemes, so `/\host`, `\/host` and `\\host`
        # reach an authority just as `//host` does — and urlparse reports no netloc for them.
        if parsed.netloc or (len(url) > 1 and url[0] in "/\\" and url[1] in "/\\"):
            return (
                "a protocol-relative '//host/path' url has no scheme; "
                f"use {self._permitted()} instead"
            )
        if url.startswith("/"):
            return None
        return "a relative path resolves against whichever page shows it; start it with '/'"

    def _permitted(self) -> str:
        """Render what this policy accepts, for the tail of a rejection message.

        Returns:
            The schemes, sorted, joined as "a, b or c"; or the rooted-path case when empty.
        """
        names = sorted(self.schemes)
        if not names:
            return "a path starting with '/'"
        if len(names) == 1:
            return names[0]
        return f"{', '.join(names[:-1])} or {names[-1]}"


#: For a URL a reader navigates to: the two that fetch a document, plus the two that hand off
#: to another application — an email address and a phone number are ordinary things to publish.
LINK_URL_POLICY = UrlPolicy(frozenset({"http", "https", "mailto", "tel"}))
