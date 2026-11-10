"""SiteConfigRepository implementation backed by a shared JSON document."""

from typing_extensions import override

from platzky.db.json_document import JsonDocument, get_site_content
from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfigRepository,
    SiteContent,
    SiteSettings,
)
from platzky.models import Footer, MenuItem, PageMeta


class JsonSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by a shared, in-memory document."""

    def __init__(self, document: JsonDocument) -> None:
        """Store a reference to the shared document.

        Args:
            document: The loaded document, shared with the other JSON
                repositories. Writes go through `JsonDocument.edit()`.
        """
        self._document = document

    def _localized(self, lang: str) -> LocalizedContent:
        """Validate the site content and return the content of a language."""
        return SiteContent.model_validate(get_site_content(self._document.data)).localized(lang)

    @override
    def get_site_settings(self, lang: str) -> SiteSettings:
        """Retrieve branding and site text for the app in a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The app's site settings, with text empty where none is configured.
        """
        content = SiteContent.model_validate(get_site_content(self._document.data))
        return SiteSettings.from_layers(content, content.localized(lang))

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
