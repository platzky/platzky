"""Locale resolution from the request host and path.

Every configured language has exactly one URL: the default language at the root of the main
host, a language with its own ``domain`` at the root of that domain, and any other language
under ``/<code>/`` on the main host.

The one exception is a route registered with ``query_locale=True``, typically a JSON API
called from pages in every language: its locale is the configured language named by the
``LOCALE_QUERY_ARG`` query argument, and the host and path only when that argument is absent
or names no configured language.
"""

import typing as t
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property

from platzky.models import LanguageCode

LANG_CODE_ARG = "lang_code"
LOCALE_QUERY_ARG = "lang"
"""Query argument naming the language of a ``query_locale`` route, e.g. ``/api/x?lang=uk``."""
RESERVED_PATH_SEGMENTS = frozenset({"lang", "static", "admin", "login", "health", "api"})


@dataclass(frozen=True)
class SiteLanguages:
    """The configured languages as URL routing sees them.

    Attributes:
        domains: Language codes mapped to their own domain, or None for a language without one.
        default: Code of the language served at the root of the main host.
    """

    domains: Mapping[LanguageCode, str | None]
    default: LanguageCode

    @cached_property
    def domainless_languages(self) -> tuple[LanguageCode, ...]:
        """Codes of the languages without their own domain, served under ``/<lang_code>/``.

        The default language is never one of them: it owns the root of the main host, even
        when no ``domain`` is configured for it.
        """
        return tuple(
            lang_code
            for lang_code, domain in self.domains.items()
            if domain is None and lang_code != self.default
        )

    @cached_property
    def domainful_languages(self) -> tuple[LanguageCode, ...]:
        """Codes of the languages served at the root of a host, never under ``/<lang_code>/``.

        These are every language with its own domain, and the default language, which owns
        the main host even when no ``domain`` is configured for it. Together with
        ``domainless_languages`` they cover every configured language.
        """
        return tuple(
            lang_code
            for lang_code, domain in self.domains.items()
            if domain is not None or lang_code == self.default
        )

    def url_prefix(self, lang_code: LanguageCode) -> str:
        """Return the URL prefix of a language, the same on every host that serves it.

        Args:
            lang_code: A configured language code.

        Returns:
            ``"/<lang_code>"`` for a domainless language; ``""`` for any other, which is
            served at the root of its host.
        """
        return f"/{lang_code}" if lang_code in self.domainless_languages else ""

    def get_host_language(self, host: str) -> LanguageCode:
        """Return the language whose ``domain`` is exactly ``host``, or the default language.

        Args:
            host: Request host, with its port if the request had one.

        Returns:
            The code of the language whose domain is ``host``, port included; the default
            language when no language claims it.
        """
        return next(
            (lang_code for lang_code, domain in self.domains.items() if domain == host),
            self.default,
        )

    def get_languages_on_host(self, host: str) -> tuple[LanguageCode, ...]:
        """Return the languages served on ``host``.

        A language's own domain serves only that language; the main host serves the default
        language and every domainless one.

        Args:
            host: Request host.

        Returns:
            The host's language first, at the host's root; then, on the main host, the
            domainless languages, each under its ``/<lang_code>`` prefix.
        """
        language = self.get_host_language(host)
        if language != self.default:
            return (language,)
        return (self.default, *self.domainless_languages)

    def get_request_language(self, host: str, path: str) -> LanguageCode:
        """Return the language a request is served in.

        Args:
            host: Request host.
            path: Request path, starting with ``/``.

        Returns:
            The language served on ``host`` named by the first segment of ``path``; else the
            language served at the host's root.
        """
        served = self.get_languages_on_host(host)
        segment = path.split("/")[1]
        return segment if segment in served else served[0]

    def get_serving_host(self, lang: LanguageCode, current_host: str) -> str:
        """Return the host that serves a language, preferring the current one.

        Args:
            lang: A configured language code.
            current_host: Host of the current request.

        Returns:
            ``current_host`` if it serves the language; otherwise the language's own domain, or
            for a domainless language the default language's domain.
        """
        if lang in self.get_languages_on_host(current_host):
            return current_host
        return self.domains.get(lang) or self.domains.get(self.default) or current_host


def any_converter(lang_codes: t.Iterable[LanguageCode]) -> str:
    """Return a URL converter matching exactly the given codes, e.g. ``any('pl', 'uk')``."""
    return "any(" + ", ".join(f"'{lang_code}'" for lang_code in lang_codes) + ")"
