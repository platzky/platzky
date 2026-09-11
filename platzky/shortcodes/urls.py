"""Policies for what URLs are allowed in a link or image position."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import NoReturn
from urllib.parse import urlparse

#: RFC 3986's scheme grammar, lowercased: the shape ``urlparse`` returns in ``.scheme``.
_SCHEME_AS_PARSED = re.compile(r"[a-z][a-z0-9+.\-]*")


class UrlFault(Enum):
    """Why a URL may not be used in the position a policy guards.

    The value is a phrase naming the fault. Every phrase is fixed here, chosen before any
    URL is seen, which is what stops a refused URL reaching a log through one — a refused
    URL being the likeliest to carry credentials or a signed query.
    """

    NO_URL = "no url was given"
    SCHEME_NOT_PERMITTED = "its scheme is not permitted here"
    PROTOCOL_RELATIVE = "a protocol-relative '//host/path' url has no scheme"
    RELATIVE_PATH = "a relative path resolves against whichever page shows it"


class UrlNotPermitted(ValueError):
    """Raised when a URL may not be used in the position a policy guards.

    A ``ValueError`` because the URL is the bad input, and a sibling of ``ShortcodeError``
    rather than a subclass: that one is fatal by design, while this one is caught per
    element, so one refused URL costs its own tag and not the page around it.
    """

    def __init__(self, fault: UrlFault, permitted: str) -> None:
        """Record the fault, and what the policy would have accepted.

        Args:
            fault: Which rule the URL broke.
            permitted: What this policy accepts, for the tail of the message.
        """
        super().__init__(f"{fault.value}; use {permitted}")
        self.fault = fault


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

    def check(self, url: str) -> None:
        """Pass a URL fit to use here, and refuse any other.

        Refused: an empty URL; a scheme outside ``schemes``, which is what keeps
        ``javascript:`` and ``data:`` out; a bare relative path such as ``photo.jpg``, which
        would resolve against whichever page shows it; and a protocol-relative
        ``//host/path`` along with its backslash spellings.

        Args:
            url: The URL as written.

        Raises:
            UrlNotPermitted: If the URL may not be used here.
        """
        if not url:
            self._refuse(UrlFault.NO_URL)
        # A browser reads '\' as '/' for a special scheme, so '/\host' and '\\host' reach an
        # authority exactly as '//host' does. Normalising first is what lets urlparse — which
        # reports no netloc for those two — answer the protocol-relative question by itself.
        parsed = urlparse(url.replace("\\", "/"))
        if parsed.scheme:
            if parsed.scheme not in self.schemes:
                self._refuse(UrlFault.SCHEME_NOT_PERMITTED)
        elif parsed.netloc:
            self._refuse(UrlFault.PROTOCOL_RELATIVE)
        elif not url.startswith("/"):
            self._refuse(UrlFault.RELATIVE_PATH)

    def _refuse(self, fault: UrlFault) -> NoReturn:
        """Refuse the URL under way, naming what this policy would have taken instead.

        Args:
            fault: Which rule the URL broke.

        Raises:
            UrlNotPermitted: Always.
        """
        names = sorted(self.schemes)
        permitted = " or ".join(filter(None, [", ".join(names[:-1]), *names[-1:]])) or (
            "a path starting with '/'"
        )
        raise UrlNotPermitted(fault, permitted)


#: For a URL a reader navigates to: the two that fetch a document, plus the two that hand
#: off to another application.
LINK_URL_POLICY = UrlPolicy(frozenset({"http", "https", "mailto", "tel"}))

#: An image source has to be something the browser can download, so this policy permits only
#: ``http`` and ``https``. ``mailto:`` and ``tel:`` hand off to another application instead,
#: which makes them fine in a link but useless as an image source. Shared by ``[image]`` and
#: ``[figure]``, the two shortcodes that render an ``<img>`` tag.
IMAGE_URL_POLICY = UrlPolicy(frozenset({"http", "https"}))
