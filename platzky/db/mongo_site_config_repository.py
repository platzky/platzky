"""SiteConfigRepository implementation backed by MongoDB collections."""

from typing import Any

from pymongo.collection import Collection
from typing_extensions import override

from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Footer, Image, MenuItem, PageMeta


class MongoSiteConfigRepository(SiteConfigRepository):
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

    @override
    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        site_config = self._get_site_config() or {}
        logo_url = site_config.get("logo_url") or ""
        return SiteSettings(
            logo=Image(url=logo_url) if logo_url else None,
            favicon_url=site_config.get("favicon_url") or "",
            primary_color=site_config.get("primary_color") or "white",
            secondary_color=site_config.get("secondary_color") or "navy",
            font=site_config.get("font") or "",
            app_description=site_config.get("app_description") or {},
        )

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
