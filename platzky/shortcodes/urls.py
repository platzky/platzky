"""Policies for what URLs are allowed in a link or image position."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

#: RFC 3986's scheme grammar, lowercased: the shape ``urlparse`` returns in ``.scheme``.
_SCHEME_AS_PARSED = re.compile(r"[a-z][a-z0-9+.\-]*")

#: ``//host/path`` reaches an authority with no scheme, and a browser reads ``\`` as ``/``
#: for special schemes, so ``/\host`` and ``\\host`` do too while ``urlparse`` reports no
#: netloc for them.
_PROTOCOL_RELATIVE = re.compile(r"[/\\]{2}")


@dataclass(frozen=True)
class UrlPolicy:
    """An allowlist of url schemes for one position, alongside the rooted-path rule."""

    schemes: frozenset[str]

    def __post_init__(self) -> None:
        """Refuse a scheme ``urlparse`` could never return, since it would match nothing.

        Raises:
            ValueError: If a declared scheme is not lowercase, or is not a scheme.
        """
        for scheme in sorted(self.schemes):  # sorted, so two faults name the same one twice
            if scheme != scheme.lower():
                raise ValueError(
                    f"url scheme {scheme!r} must be lowercase; write {scheme.lower()!r}"
                )
            if not _SCHEME_AS_PARSED.fullmatch(scheme):
                raise ValueError(
                    f"{scheme!r} is not a url scheme: a letter, then letters, digits, "
                    f"'+', '-' or '.'"
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
        parsed = urlparse(url)
        if parsed.scheme:
            if parsed.scheme in self.schemes:
                return None
            return f"scheme {parsed.scheme!r} is not allowed; use {self._permitted()}"
        if parsed.netloc or _PROTOCOL_RELATIVE.match(url):
            return (
                "a protocol-relative '//host/path' url has no scheme; "
                f"use {self._permitted()} instead"
            )
        if url.startswith("/"):
            return None
        return "a relative path resolves against whichever page shows it; start it with '/'"

    def _permitted(self) -> str:
        """Name what this policy accepts, for the tail of a rejection message.

        Returns:
            The schemes, sorted, joined as "a, b or c"; or the rooted-path case when empty.
        """
        names = sorted(self.schemes)
        if not names:
            return "a path starting with '/'"
        if len(names) == 1:
            return names[0]
        return f"{', '.join(names[:-1])} or {names[-1]}"


#: For a URL a reader navigates to: the two that fetch a document, plus the two that hand
#: off to another application.
LINK_URL_POLICY = UrlPolicy(frozenset({"http", "https", "mailto", "tel"}))
