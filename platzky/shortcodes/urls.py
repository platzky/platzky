"""Policies for what URLs are allowed in a link or image position."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

#: RFC 3986's scheme grammar, lowercased: the shape ``urlparse`` returns in ``.scheme``.
_SCHEME_AS_PARSED = re.compile(r"[a-z][a-z0-9+.\-]*")


class UrlFault(Enum):
    """Why a URL may not be used in the position a policy guards.

    The value is a phrase naming the fault, for whoever reports it. It describes the URL's
    shape and never quotes the URL back, a refused one being the likeliest to carry
    credentials or a signed query — so it is safe to log verbatim.
    """

    NO_URL = "no url was given"
    SCHEME_NOT_PERMITTED = "its scheme is not permitted here"
    PROTOCOL_RELATIVE = "a protocol-relative '//host/path' url has no scheme"
    RELATIVE_PATH = "a relative path resolves against whichever page shows it"


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
        return self.fault(url) is None

    def fault(self, url: str) -> UrlFault | None:
        """Classify this URL against the policy.

        Refused: an empty URL; a scheme outside ``schemes``, which is what keeps
        ``javascript:`` and ``data:`` out; a bare relative path such as ``photo.jpg``, which
        would resolve against whichever page shows it; and a protocol-relative
        ``//host/path`` along with its backslash spellings.

        Args:
            url: The URL as written.

        Returns:
            The fault that refuses it, or ``None`` if the URL may be used.
        """
        if not url:
            return UrlFault.NO_URL
        # A browser reads '\' as '/' for a special scheme, so '/\host' and '\\host' reach an
        # authority exactly as '//host' does. Normalising first is what lets urlparse — which
        # reports no netloc for those two — answer the protocol-relative question by itself.
        parsed = urlparse(url.replace("\\", "/"))
        if parsed.scheme:
            return None if parsed.scheme in self.schemes else UrlFault.SCHEME_NOT_PERMITTED
        if parsed.netloc:
            return UrlFault.PROTOCOL_RELATIVE
        return None if url.startswith("/") else UrlFault.RELATIVE_PATH

    def permits(self) -> str:
        """Name what this policy accepts, for whoever reports a fault.

        Returns:
            The schemes, sorted, joined as "a, b or c"; or the rooted-path case when empty.
        """
        names = sorted(self.schemes)
        return " or ".join(filter(None, [", ".join(names[:-1]), *names[-1:]])) or (
            "a path starting with '/'"
        )


#: For a URL a reader navigates to: the two that fetch a document, plus the two that hand
#: off to another application.
LINK_URL_POLICY = UrlPolicy(frozenset({"http", "https", "mailto", "tel"}))
