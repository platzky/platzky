"""SiteConfigRepository implementation backed by MongoDB collections."""

from typing import Any

from pymongo.collection import Collection
from typing_extensions import override

from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Footer, MenuItem, PageMeta


class MongoSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by MongoDB collections.

    Site settings are stored as a single document (``{"_id": "config", ...}``)
    in the site_content collection, fetched once per `get_site_settings()` call
    instead of once per field. Per-language text overrides are one document per
    language (``{"_id": "<lang>", ...}``) in the localized_content collection;
    ``localized_content`` inside the config document is not read.
    """

    def __init__(
        self,
        site_content: Collection[Any],
        menu_items: Collection[Any],
        localized_content: Collection[Any],
    ) -> None:
        """Store references to the shared collections.

        Args:
            site_content: The database's ``site_content`` collection.
            menu_items: The database's ``menu_items`` collection.
            localized_content: The database's ``localized_content`` collection.
        """
        self._site_content = site_content
        self._menu_items = menu_items
        self._localized_content = localized_content

    def _get_site_config(self) -> dict[str, Any] | None:
        """Retrieve the site configuration document."""
        return self._site_content.find_one({"_id": "config"})

    @override
    def get_site_settings(self, lang: str) -> SiteSettings:
        """Retrieve branding and site text for the app in a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The app's site settings, with text empty where none is configured.
        """
        projection = list(SiteSettings.STORED_KEYS)
        config = self._site_content.find_one({"_id": "config"}, projection=projection)
        localized = self._localized_content.find_one({"_id": lang}, projection=projection)
        return SiteSettings.from_layers(config or {}, localized or {}, lang)

    @override
    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Menu items in that language.
        """
        menu_items_doc = self._menu_items.find_one({"_id": lang})
        items = (menu_items_doc or {}).get("items") or []
        return [MenuItem.model_validate(item) for item in items]

    @override
    def get_home_page_path(self, locale: str) -> str | None:
        """Retrieve the site-relative path configured as the site's homepage.

        ``home_page_path`` may be a single string (applies to every locale) or a
        dict mapping locale codes to paths, with an optional "default" key used
        when the current locale has no entry of its own.

        Args:
            locale: Language code (e.g., 'en', 'pl') of the current request.

        Returns:
            Homepage path, or None if no homepage override is configured.
        """
        site_config = self._get_site_config()
        home_page_path = site_config.get("home_page_path") if site_config else None
        if isinstance(home_page_path, dict):
            return home_page_path.get(locale, home_page_path.get("default"))
        return home_page_path

    @override
    def get_blog_meta(self, lang: str) -> PageMeta:
        """Retrieve the blog index's title and description for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The blog meta, empty if none is configured for the language.
        """
        site_config = self._get_site_config() or {}
        blog_meta = site_config.get("blog_meta") or {}
        return PageMeta(**(blog_meta.get(lang) or {}))

    @override
    def get_footer(self, lang: str) -> Footer:
        """Retrieve the site-wide footer for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The footer, empty and not collapsible if none is configured.
        """
        # Explicit nulls count as missing: the footer is rendered on every page.
        footer = (self._get_site_config() or {}).get("footer") or {}
        return Footer(
            content=(footer.get("content") or {}).get(lang) or "",
            collapsible=bool(footer.get("collapsible", False)),
        )
