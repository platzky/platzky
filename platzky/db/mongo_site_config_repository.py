"""SiteConfigRepository implementation backed by MongoDB collections."""

from collections.abc import Mapping
from typing import Any

from pymongo.collection import Collection
from typing_extensions import override

from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfigRepository,
    SiteContent,
    SiteSettings,
    parse_site_content,
)
from platzky.models import Footer, MenuItem, PageMeta


def _without_id(document: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a stored document's fields without its ``_id``, empty if there is no document."""
    return {key: value for key, value in (document or {}).items() if key != "_id"}


class MongoSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by MongoDB collections.

    The site-wide keys of `SiteContent` are one document (``{"_id": "config", ...}``) in the
    site_content collection. The `LocalizedContent` of each language is one document
    (``{"_id": "<lang>", ...}``) in the localized_content collection.
    """

    def __init__(
        self,
        site_content: Collection[Any],
        localized_content: Collection[Any],
    ) -> None:
        """Store references to the shared collections.

        Args:
            site_content: The database's ``site_content`` collection.
            localized_content: The database's ``localized_content`` collection.
        """
        self._site_content = site_content
        self._localized_content = localized_content

    def _localized(self, lang: str) -> LocalizedContent:
        """Read the document of a language."""
        document = self._localized_content.find_one({"_id": lang})
        return LocalizedContent.model_validate(_without_id(document))

    def validate(self) -> None:
        """Read the whole site content once and check it against the site content format.

        Raises:
            InvalidSiteContentError: If the config document or a language document is invalid;
                unknown keys are reported too.
        """
        parse_site_content(
            {
                **_without_id(self._site_content.find_one({"_id": "config"})),
                "localized_content": {
                    document["_id"]: _without_id(document)
                    for document in self._localized_content.find()
                },
            }
        )

    @override
    def get_site_settings(self, lang: str) -> SiteSettings:
        """Retrieve branding and site text for the app in a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The app's site settings, with text empty where none is configured.
        """
        config = self._site_content.find_one({"_id": "config"})
        return SiteSettings.from_layers(
            SiteContent.model_validate(_without_id(config)),
            self._localized(lang),
        )

    @override
    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Menu items in that language.
        """
        return list(self._localized(lang).menu_items)

    @override
    def get_home_page_path(self, locale: str) -> str | None:
        """Retrieve the site-relative path configured as the site's homepage.

        Args:
            locale: Language code (e.g., 'en', 'pl') of the current request.

        Returns:
            Homepage path, or None if no homepage override is configured for
            this locale.
        """
        return self._localized(locale).home_page_path or None

    @override
    def get_blog_meta(self, lang: str) -> PageMeta:
        """Retrieve the blog index's title and description for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The blog meta, empty if none is configured for the language.
        """
        return self._localized(lang).blog_meta

    @override
    def get_footer(self, lang: str) -> Footer:
        """Retrieve the site-wide footer for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The footer, empty and not collapsible if none is configured.
        """
        return self._localized(lang).footer
