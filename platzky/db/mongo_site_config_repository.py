"""SiteConfigRepository implementation backed by MongoDB collections."""

from typing import Any

from pymongo.collection import Collection

from platzky.db.site_config_repository import SiteSettings
from platzky.models import Image, MenuItem


class MongoSiteConfigRepository:
    """Site config repository backed by MongoDB collections.

    Site settings are stored as a single document (``{"_id": "config", ...}``)
    in the site_content collection, fetched once per `get_site_settings()` call
    instead of once per old getter.
    """

    def __init__(self, site_content: Collection[Any], menu_items: Collection[Any]) -> None:
        """Store references to the shared collections.

        Args:
            site_content: The database's ``site_content`` collection.
            menu_items: The database's ``menu_items`` collection.
        """
        self._site_content = site_content
        self._menu_items = menu_items

    def _get_site_config(self) -> dict[str, Any] | None:
        """Retrieve the site configuration document."""
        return self._site_content.find_one({"_id": "config"})

    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        site_config = self._get_site_config()
        logo_url = site_config.get("logo_url", "") if site_config else ""
        return SiteSettings(
            logo=Image(url=logo_url) if logo_url else None,
            favicon_url=site_config.get("favicon_url", "") if site_config else "",
            primary_color=site_config.get("primary_color", "white") if site_config else "white",
            secondary_color=(site_config.get("secondary_color", "navy") if site_config else "navy"),
            font=site_config.get("font", "") if site_config else "",
            app_description=site_config.get("app_description", {}) if site_config else {},
        )

    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Menu items in that language.
        """
        menu_items_doc = self._menu_items.find_one({"_id": lang})
        if menu_items_doc and "items" in menu_items_doc:
            return [MenuItem.model_validate(item) for item in menu_items_doc["items"]]
        return []

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
