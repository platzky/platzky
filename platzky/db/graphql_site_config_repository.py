"""SiteConfigRepository implementation backed by a GraphQL (Hygraph) CMS."""

from collections.abc import Mapping
from typing import Any, Callable

from gql import Client, gql
from typing_extensions import override

from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfigRepository,
    SiteContent,
    SiteSettings,
)
from platzky.models import Footer, MenuItem, PageMeta

_SITE_FIELDS = """
        appName
        appTitle
        appDescription
        logo { image { url } }
        faviconUrl
        primaryColor
        secondaryColor
        font { name url }
"""

_LOCALIZED_FIELDS = """
        appName
        appTitle
        appDescription
        logo { image { url } }
        homePagePath
        blogMeta { title description }
        footer { content collapsible }
        menuItems { name url }
"""

_LOCALIZED = "localized: localizedContent(where: {language: $lang}, stage: PUBLISHED) {"

_SITE_SETTINGS_QUERY = (
    "query SiteSettings($lang: Lang!) {\n"
    "  site: sites(stage: PUBLISHED, first: 1) {"
    + _SITE_FIELDS
    + "  }\n  "
    + _LOCALIZED
    + _LOCALIZED_FIELDS
    + "  }\n}"
)

_CONTENT_QUERY = (
    "query LocalizedContent($lang: Lang!) {\n  " + _LOCALIZED + _LOCALIZED_FIELDS + "  }\n}"
)


def _present(values: Mapping[str, Any]) -> dict[str, Any]:
    """Drop the null and empty values, so they fall through to the next source.

    Hygraph answers null for every field an editor left unset, so here null means "not set";
    it is not a validation of the site content.
    """
    return {key: value for key, value in values.items() if value}


def _logo_url(entry: Mapping[str, Any]) -> str | None:
    """Return the URL of the entry's logo, None if the logo or its image is not set."""
    url: str | None = ((entry.get("logo") or {}).get("image") or {}).get("url")
    return url


def _site_content(entry: Mapping[str, Any]) -> SiteContent:
    """Map a `Site` CMS entry to the shared model; null and missing fields are not set."""
    return SiteContent.model_validate(
        {
            **_present(
                {
                    "app_name": entry.get("appName"),
                    "app_title": entry.get("appTitle"),
                    "app_description": entry.get("appDescription"),
                    "logo_url": _logo_url(entry),
                    "favicon_url": entry.get("faviconUrl"),
                    "primary_color": entry.get("primaryColor"),
                    "secondary_color": entry.get("secondaryColor"),
                }
            ),
            "font": _present(entry.get("font") or {}),
        }
    )


def _localized_content(entry: Mapping[str, Any]) -> LocalizedContent:
    """Map a `LocalizedContent` CMS entry to the shared model.

    Args:
        entry: The CMS entry, or an empty mapping for a language without one.

    Returns:
        The entry's content; null and missing fields are not set.
    """
    return LocalizedContent.model_validate(
        {
            **_present(
                {
                    "app_name": entry.get("appName"),
                    "app_title": entry.get("appTitle"),
                    "app_description": entry.get("appDescription"),
                    "logo_url": _logo_url(entry),
                    "home_page_path": entry.get("homePagePath"),
                }
            ),
            "blog_meta": _present(entry.get("blogMeta") or {}),
            "footer": _present(entry.get("footer") or {}),
            "menu_items": entry.get("menuItems", []),
        }
    )


class GraphQLSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by a GraphQL CMS.

    The `Site` model (one entry) holds the site-wide content, and the `LocalizedContent`
    model holds one entry per language (`language` is required and unique). The server
    picks the entry of the requested language, so each method makes one request.
    """

    def __init__(self, client_getter: Callable[[], Client]) -> None:
        """Store the client source.

        Args:
            client_getter: Zero-argument callable returning the GraphQL client to
                use for the current thread.
        """
        self._client_getter = client_getter

    def _content(self, lang: str) -> LocalizedContent:
        """Fetch the `LocalizedContent` entry of a language."""
        result = self._client_getter().execute(gql(_CONTENT_QUERY), variable_values={"lang": lang})
        return _localized_content(result["localized"] or {})

    @override
    def get_site_settings(self, lang: str) -> SiteSettings:
        """Retrieve branding and site text for the app in a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The app's site settings, with text empty where none is configured.
        """
        result = self._client_getter().execute(
            gql(_SITE_SETTINGS_QUERY), variable_values={"lang": lang}
        )
        return SiteSettings.from_layers(
            _site_content(next(iter(result["site"]), {})),
            _localized_content(result["localized"] or {}),
        )

    @override
    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Menu items in that language.
        """
        return list(self._content(lang).menu_items)

    @override
    def get_home_page_path(self, locale: str) -> str | None:
        """Retrieve the site-relative path configured as the site's homepage.

        Args:
            locale: Language code (e.g., 'en', 'pl') of the current request.

        Returns:
            Homepage path, or None if no homepage override is configured for
            this locale.
        """
        return self._content(locale).home_page_path or None

    @override
    def get_blog_meta(self, lang: str) -> PageMeta:
        """Retrieve the blog index's title and description for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The blog meta, empty if none is configured for the language.
        """
        return self._content(lang).blog_meta

    @override
    def get_footer(self, lang: str) -> Footer:
        """Retrieve the site-wide footer for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The footer, empty and not collapsible if none is configured.
        """
        return self._content(lang).footer
