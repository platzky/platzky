"""Protocol for site-wide configuration: branding, menu, and home page.

Every app needs branding (logo, colors, font, description), a nav menu, and a
home page regardless of whether it has a blog, so this is kept separate from
`BlogStorage` and `PluginConfigRepository`.
"""

from typing import Protocol

from pydantic import BaseModel, Field

from platzky.models import Image, MenuItem


class SiteSettings(BaseModel):
    """Branding and description for the app, resolved as a single unit."""

    logo: Image | None = None
    favicon_url: str = ""
    primary_color: str = "white"
    secondary_color: str = "navy"
    font: str = ""
    app_description: dict[str, str] = Field(default_factory=dict)


class SiteConfigRepository(Protocol):
    """Repository for site-wide branding, navigation, and home page config."""

    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        ...

    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Menu items in that language.
        """
        ...

    def get_home_page_path(self, locale: str) -> str | None:
        """Retrieve the site-relative path configured as the site's homepage.

        Args:
            locale: Language code (e.g., 'en', 'pl') of the current request.

        Returns:
            Homepage path, or None if no homepage override is configured.
        """
        ...
