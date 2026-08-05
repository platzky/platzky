"""SiteConfigRepository implementation backed by a shared JSON document."""

from typing import Any

from platzky.db.json_document import get_site_content
from platzky.db.site_config_repository import SiteSettings
from platzky.models import Image, MenuItem


class JsonSiteConfigRepository:
    """Site config repository backed by a shared, in-memory document."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Store a reference to the shared document.

        Args:
            data: The loaded document, shared with whatever else (blog
                storage, plugin config) reads from the same backing store.
        """
        self._data = data

    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        site_content = get_site_content(self._data)
        logo_url = site_content.get("logo_url", "")
        return SiteSettings(
            logo=Image(url=logo_url) if logo_url else None,
            favicon_url=site_content.get("favicon_url", ""),
            primary_color=site_content.get("primary_color", "white"),
            secondary_color=site_content.get("secondary_color", "navy"),
            font=site_content.get("font", ""),
            app_description=site_content.get("app_description", {}),
        )

    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Menu items in that language.
        """
        menu_items_raw = get_site_content(self._data).get("menu_items", {})
        items_in_lang = menu_items_raw.get(lang, [])
        return [MenuItem.model_validate(x) for x in items_in_lang]

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
        home_page_path = get_site_content(self._data).get("home_page_path")
        if isinstance(home_page_path, dict):
            return home_page_path.get(locale, home_page_path.get("default"))
        return home_page_path
