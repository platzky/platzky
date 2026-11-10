"""SiteConfigRepository implementation backed by a GraphQL (Hygraph) CMS."""

from collections.abc import Mapping
from typing import Any, Callable

from gql import Client, gql
from typing_extensions import override

from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfigRepository,
    SiteContent,
)

# The text fields that `Site` and `LocalizedContent` both have, answered in snake_case.
_TEXT_FIELDS = """
    app_name: appName
    app_title: appTitle
    app_description: appDescription
    logo { image { url } }
"""

_SITE_CONTENT_QUERY = (
    "query SiteContent {\n  sites(stage: PUBLISHED, first: 1) {"
    + _TEXT_FIELDS
    + """    favicon_url: faviconUrl
    primary_color: primaryColor
    secondary_color: secondaryColor
    font { name url }
  }
}"""
)

_LOCALIZED_CONTENT_QUERY = (
    "query LocalizedContent($lang: Lang!) {\n"
    "  localizedContent(where: {language: $lang}, stage: PUBLISHED) {"
    + _TEXT_FIELDS
    + """    home_page_path: homePagePath
    blog_meta: blogMeta { title description }
    footer { content collapsible }
    menu_items: menuItems { name url }
  }
}"""
)


def _present(values: Mapping[str, Any]) -> dict[str, Any]:
    """Drop the null and empty-string values, also in nested objects, so they fall through.

    Hygraph answers null for every field an editor left unset, so here null means "not set";
    it is not a validation of the site content.
    """
    return {
        key: _present(value) if isinstance(value, Mapping) else value
        for key, value in values.items()
        if value is not None and value != ""
    }


def _fields(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Return the entry's set fields, with the nested ``logo.image.url`` as ``logo_url``."""
    logo_url = ((entry.get("logo") or {}).get("image") or {}).get("url")
    return _present(
        {**{key: value for key, value in entry.items() if key != "logo"}, "logo_url": logo_url}
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
    def get_site_content(self) -> SiteContent:
        """Retrieve the site-wide content.

        Returns:
            The site-wide content; null and missing fields are not set.
        """
        result = self._client_getter().execute(gql(_SITE_CONTENT_QUERY))
        return SiteContent.model_validate(_fields(next(iter(result["sites"]), {})))

    @override
    def get_localized_content(self, lang: str) -> LocalizedContent:
        """Retrieve the content of one language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The language's content, empty if none is configured for it; null and missing
            fields are not set.
        """
        result = self._client_getter().execute(
            gql(_LOCALIZED_CONTENT_QUERY), variable_values={"lang": lang}
        )
        return LocalizedContent.model_validate(_fields(result["localizedContent"] or {}))
