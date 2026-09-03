"""Policies for what URLs are allowed in a link or image position."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

#: A scheme as RFC 3986 spells it, narrowed to lowercase because that is what ``urlparse``
#: hands back. Deliberately *not* a list of the schemes that exist: this class is an
#: allowlist, and which schemes are safe in a given position is not the same question as
#: which ones are registered — ``data:`` is registered and is exactly what a policy like
#: this exists to refuse, while a private ``myapp:`` is unregistered and perfectly fine for
#: the application that owns it. Only the policy's author can answer the first question, so
#: the check here is syntax and nothing more.
_SCHEME_RE = re.compile(r"[a-z][a-z0-9+.\-]*")


@dataclass(frozen=True)
class UrlPolicy:
    """
    A policy for what URLs are allowed in a URL.
    """

    schemes: frozenset[str]

    def __post_init__(self) -> None:
        """Refuse a declared scheme ``urlparse`` could never hand back.

        Both faults it catches fail the same silent way: the scheme matches nothing, so the
        policy quietly refuses every URL it was written to allow, and then advises the very
        scheme it just rejected. Raising here puts that in front of whoever wrote the
        policy, at construction, instead of leaving it to be found as a missing link.

        Rejecting rather than quietly lowercasing, because ``UrlPolicy`` is public API and
        a security control: silently rewriting a security declaration into something its
        author did not write is not a favour worth doing, and there is no correct reading
        of a scheme that is not a scheme.

        Raises:
            ValueError: If a declared scheme is not lowercase, or is not a scheme at all.
        """
        # Sorted so a policy with more than one fault names the same scheme every run.
        for scheme in sorted(self.schemes):
            if scheme != scheme.lower():
                raise ValueError(
                    f"UrlPolicy scheme {scheme!r} must be lowercase: urlparse lowercases "
                    f"what it parses, so this would match nothing. Write {scheme.lower()!r}."
                )
            if not _SCHEME_RE.fullmatch(scheme):
                raise ValueError(
                    f"UrlPolicy scheme {scheme!r} is not a url scheme: a scheme is a letter "
                    f"followed by letters, digits, '+', '-' or '.' (RFC 3986), and carries "
                    f"no ':'."
                )

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
