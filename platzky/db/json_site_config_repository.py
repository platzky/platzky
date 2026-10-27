"""SiteConfigRepository implementation backed by a shared JSON document."""

from typing_extensions import override

from platzky.db.json_document import JsonDocument, get_site_content
from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Footer, Image, MenuItem, PageMeta


class JsonSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by a shared, in-memory document."""

    def __init__(self, document: JsonDocument) -> None:
        """Store a reference to the shared document.

        Args:
            document: The loaded document, shared with the other JSON
                repositories. Writes go through `JsonDocument.edit()`.
        """
        self._document = document

    @override
    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        site_content = get_site_content(self._document.data)
        logo_url = site_content.get("logo_url") or ""
        return SiteSettings(
            logo=Image(url=logo_url) if logo_url else None,
            favicon_url=site_content.get("favicon_url") or "",
            primary_color=site_content.get("primary_color") or "white",
            secondary_color=site_content.get("secondary_color") or "navy",
            font=site_content.get("font") or "",
            app_description=site_content.get("app_description") or {},
        )

    @override
    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Menu items in that language.
        """
        menu_items_raw = get_site_content(self._document.data).get("menu_items") or {}
        return [MenuItem.model_validate(x) for x in menu_items_raw.get(lang) or []]

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
        home_page_path = get_site_content(self._document.data).get("home_page_path")
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
        blog_meta = get_site_content(self._document.data).get("blog_meta") or {}
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
        footer = get_site_content(self._document.data).get("footer") or {}
        return Footer(
            content=(footer.get("content") or {}).get(lang) or "",
            collapsible=bool(footer.get("collapsible", False)),
        )
