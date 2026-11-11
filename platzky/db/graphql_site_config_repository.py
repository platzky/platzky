"""SiteConfigRepository implementation backed by a GraphQL (Hygraph) CMS."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Callable

from gql import Client, gql
from typing_extensions import override

from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfig,
    SiteConfigRepository,
)
from platzky.models import LanguageCode

_SITE_CONFIG_QUERY = gql("""
    query SiteConfig {
      sites(stage: PUBLISHED, first: 1) {
        app_name: appName
        app_title: appTitle
        app_description: appDescription
        logo_url: logoUrl
        favicon_url: faviconUrl
        primary_color: primaryColor
        secondary_color: secondaryColor
        font { name url }
      }
    }
    """)

_LOCALIZED_CONTENT_QUERY = gql("""
    query LocalizedContent($lang: Lang!) {
      localizedContent(where: {language: $lang}, stage: PUBLISHED) {
        app_name: appName
        app_title: appTitle
        app_description: appDescription
        logo_url: logoUrl
        home_page_path: homePagePath
        footer { content collapsible }
        menu_items: menuItems { name url }
      }
    }
    """)


def _without_unset(values: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the fields an editor set, also in nested objects, so the rest take defaults.

    This is not a validation of the site content: in Hygraph, null means "not set".
    """
    return MappingProxyType(
        {
            key: _without_unset(value) if isinstance(value, Mapping) else value
            for key, value in values.items()
            if value not in (None, "")
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

    @override
    def get_site_config(self) -> SiteConfig:
        """Retrieve the site-wide content.

        Returns:
            The site-wide content; null and missing fields are not set.
        """
        result = self._client_getter().execute(_SITE_CONFIG_QUERY)
        return SiteConfig.model_validate(_without_unset(next(iter(result["sites"]), {})))

    @override
    def get_localized_content(self, lang: LanguageCode) -> LocalizedContent:
        """Retrieve the content of one language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The language's content, empty if none is configured for it; null and missing
            fields are not set.
        """
        result = self._client_getter().execute(
            _LOCALIZED_CONTENT_QUERY, variable_values={"lang": lang}
        )
        return LocalizedContent.model_validate(_without_unset(result["localizedContent"] or {}))
