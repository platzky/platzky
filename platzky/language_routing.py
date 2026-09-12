"""Locale resolution from the request host and path.

Every configured language has exactly one URL: the default language at the root of the main
host, a language with its own ``domain`` at the root of that domain, and any other language
under ``/<code>/`` on the main host.
"""

import typing as t

if t.TYPE_CHECKING:
    from platzky.config import Config, LanguageConfig

LANG_CODE_ARG = "lang_code"
RESERVED_PATH_SEGMENTS = frozenset({"lang", "static", "admin", "login", "health", "api"})


def normalize_domain(domain: str) -> str:
    """Return a domain or host lowercased, without a trailing dot or a leading ``www.``."""
    return domain.rstrip(".").lower().removeprefix("www.")


def language_for_host(languages: t.Mapping[str, "LanguageConfig"], host: str) -> str | None:
    """Return the language whose ``domain`` matches ``host``.

    A domain with an explicit port must match the host's port exactly; a domain without one
    matches regardless of port (e.g. behind a proxy that forwards on a non-standard port).

    Args:
        languages: Configured languages keyed by code.
        host: Request host, optionally with a port.

    Returns:
        The matching language code, or None if no language claims ``host``.
    """
    host_with_port = normalize_domain(host)
    host_without_port = normalize_domain(host.split(":", 1)[0])
    for code, language in languages.items():
        if language.domain is None:
            continue
        domain = normalize_domain(language.domain)
        if domain == (host_with_port if ":" in domain else host_without_port):
            return code
    return None


def dedicated_language(config: "Config", host: str) -> str | None:
    """Return the non-default language whose own domain is ``host``, if any."""
    code = language_for_host(config.languages, host)
    return code if code != config.default_language else None


def resolve_locale(config: "Config", host: str, path: str) -> str:
    """Return the language a request is served in.

    Args:
        config: Application configuration.
        host: Request host.
        path: Request path.

    Returns:
        The language whose own domain is ``host``; else the path language whose prefix
        ``path`` starts with; else the default language.
    """
    if code := dedicated_language(config, host):
        return code
    for lang in config.path_languages:
        if path == f"/{lang}" or path.startswith(f"/{lang}/"):
            return lang
    return config.default_language


def served_languages(config: "Config", host: str) -> dict[str, str]:
    """Map each language served on ``host`` to its URL prefix.

    Args:
        config: Application configuration.
        host: Request host.

    Returns:
        ``{code: ""}`` on a language's own domain; otherwise the default language with an
        empty prefix plus every path language with ``"/<code>"``.
    """
    if code := dedicated_language(config, host):
        return {code: ""}
    return {config.default_language: "", **{lang: f"/{lang}" for lang in config.path_languages}}


def language_home_url(config: "Config", lang: str, scheme: str, host: str) -> str:
    """Return the absolute URL of a language's home page, valid from any host.

    Args:
        config: Application configuration.
        lang: Language code to link to.
        scheme: URL scheme of the current request.
        host: Host of the current request.

    Returns:
        The root of the language's own domain for a domain language. For the default and path
        languages, ``/`` or ``/<code>/`` on the current host, or on the default language's
        domain when the current host belongs to another language.
    """
    languages = config.languages
    language = languages.get(lang)
    if language and language.domain and lang != config.default_language:
        return f"{scheme}://{_apply_www(language.domain, config.use_www)}/"
    default = languages.get(config.default_language)
    if default and default.domain and dedicated_language(config, host):
        host = _apply_www(default.domain, config.use_www)
    prefix = "" if lang == config.default_language else f"/{lang}"
    return f"{scheme}://{host}{prefix}/"


def _apply_www(domain: str, use_www: bool) -> str:
    """Return ``domain`` in the form the ``USE_WWW`` redirect would send visitors to."""
    bare = normalize_domain(domain)
    return f"www.{bare}" if use_www else bare
