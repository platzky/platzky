"""Locale resolution from the request host and path.

Every configured language has exactly one URL: the default language at the root of the main
host, a language with its own ``domain`` at the root of that domain, and any other language
under ``/<code>/`` on the main host.
"""

import typing as t
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property

LANG_CODE_ARG = "lang_code"
RESERVED_PATH_SEGMENTS = frozenset({"lang", "static", "admin", "login", "health", "api"})


@dataclass(frozen=True)
class SiteLanguages:
    """The configured languages as URL routing sees them.

    Attributes:
        domains: Language codes mapped to their own domain, or None for a language without one.
        default: Code of the language served at the root of the main host.
    """

    domains: Mapping[str, str | None]
    default: str

    @cached_property
    def domainless_languages(self) -> tuple[str, ...]:
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
    def domainful_languages(self) -> tuple[str, ...]:
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

    def url_prefix(self, lang_code: str) -> str:
        """Return the URL prefix of a language, the same on every host that serves it.

        Args:
            lang_code: A configured language code.

        Returns:
            ``"/<lang_code>"`` for a domainless language; ``""`` for any other, which is
            served at the root of its host.
        """
        return f"/{lang_code}" if lang_code in self.domainless_languages else ""


def any_converter(lang_codes: t.Iterable[str]) -> str:
    """Return a URL converter matching exactly the given codes, e.g. ``any('pl', 'uk')``."""
    return "any(" + ", ".join(f"'{lang_code}'" for lang_code in lang_codes) + ")"


def language_for_host(languages: SiteLanguages, host: str) -> str:
    """Return the language whose ``domain`` is exactly ``host``, or the default language.

    Args:
        languages: The site's languages.
        host: Request host, with its port if the request had one.

    Returns:
        The code of the language whose domain is ``host``, port included; the default language
        when no language claims it.
    """
    return next(
        (lang_code for lang_code, domain in languages.domains.items() if domain == host),
        languages.default,
    )


def served_languages(languages: SiteLanguages, host: str) -> dict[str, str]:
    """Map each language served on ``host`` to its URL prefix.

    Args:
        languages: The site's languages.
        host: Request host.

    Returns:
        The host's language with an empty prefix; on the main host, also every domainless
        language with ``"/<lang_code>"``.
    """
    host_language = language_for_host(languages, host)
    on_main_host = host_language == languages.default
    served = [host_language, *(languages.domainless_languages if on_main_host else ())]
    return {lang: languages.url_prefix(lang) for lang in served}


def resolve_locale(languages: SiteLanguages, host: str, path: str) -> str:
    """Return the language a request is served in.

    Args:
        languages: The site's languages.
        host: Request host.
        path: Request path.

    Returns:
        The language served on ``host`` whose prefix ``path`` starts with; else the language
        served at the host's root.
    """
    return next(
        (
            lang
            for lang, prefix in served_languages(languages, host).items()
            if prefix and (path == prefix or path.startswith(f"{prefix}/"))
        ),
        language_for_host(languages, host),
    )


def language_url(
    languages: SiteLanguages, lang: str, scheme: str, host: str, path: str = "/"
) -> str:
    """Return the absolute URL of a page in a language, valid from any host.

    Args:
        languages: The site's languages.
        lang: A configured language code to link to.
        scheme: URL scheme of the current request.
        host: Host of the current request.
        path: Path of the page without any language prefix; the home page by default.

    Returns:
        ``path`` under the language's prefix on the current host if it serves the language;
        otherwise on the host that does: the language's own domain, or for a domainless
        language the default language's domain.
    """
    serving_host = (
        host
        if lang in served_languages(languages, host)
        else languages.domains.get(lang) or languages.domains.get(languages.default) or host
    )
    return f"{scheme}://{serving_host}{languages.url_prefix(lang)}{path}"
