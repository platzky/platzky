"""Policies for what URLs are allowed in a link or image position."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

#: RFC 3986's scheme grammar, lowercased: the shape ``urlparse`` returns in ``.scheme``.
_SCHEME_AS_PARSED = re.compile(r"[a-z][a-z0-9+.\-]*")


@dataclass(frozen=True)
class UrlPolicy:
    """An allowlist of url schemes for one position, alongside the rooted-path rule."""

    schemes: frozenset[str]

    def __post_init__(self) -> None:
        """Refuse a scheme ``urlparse`` could never return, since it would match nothing.

        Uppercase is the case worth naming: ``.scheme`` is lowercased, so ``HTTPS`` matches
        nothing while advising the very scheme it had just refused. It is refused where it is
        written rather than silently lowercased — this is a security declaration, and its
        author is entitled to have it mean what they wrote.

        Raises:
            ValueError: If a declared scheme is not the shape ``urlparse`` returns.
        """
        for scheme in sorted(self.schemes):  # sorted, so two faults name the same one twice
            if not _SCHEME_AS_PARSED.fullmatch(scheme):
                raise ValueError(
                    f"{scheme!r} is not a url scheme: a lowercase letter, then letters, "
                    f"digits, '+', '-' or '.'"
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

        Refused: an empty URL; a scheme outside ``schemes``, which is what keeps
        ``javascript:`` and ``data:`` out; a bare relative path such as ``photo.jpg``, which
        would resolve against whichever page shows it; and a protocol-relative
        ``//host/path`` along with its backslash spellings.

        Args:
            url: The URL as written.

        Returns:
            A phrase naming the fault, safe to log verbatim — it quotes back the scheme but
            never the URL, a rejected one being the likeliest to carry credentials or a
            signed query — or ``None`` if the URL is fine.
        """
        if not url:
            return "no url was given"
        # A browser reads '\' as '/' for a special scheme, so '/\host' and '\\host' reach an
        # authority exactly as '//host' does. Normalising first is what lets urlparse — which
        # reports no netloc for those two — answer the protocol-relative question by itself.
        parsed = urlparse(url.replace("\\", "/"))
        names = sorted(self.schemes)
        permitted = " or ".join(filter(None, [", ".join(names[:-1]), *names[-1:]])) or (
            "a path starting with '/'"
        )
        if parsed.scheme:
            if parsed.scheme in self.schemes:
                return None
            return f"scheme {parsed.scheme!r} is not allowed; use {permitted}"
        if parsed.netloc:
            return f"a protocol-relative '//host/path' url has no scheme; use {permitted} instead"
        if url.startswith("/"):
            return None
        return "a relative path resolves against whichever page shows it; start it with '/'"


#: For a URL a reader navigates to: the two that fetch a document, plus the two that hand
#: off to another application.
LINK_URL_POLICY = UrlPolicy(frozenset({"http", "https", "mailto", "tel"}))
