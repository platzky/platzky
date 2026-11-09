"""Protocol for site-wide configuration: branding, menu, home page, footer, and blog meta.

Every app needs branding (logo, colors, font, description), a nav menu, and a
home page regardless of whether it has a blog, so this is kept separate from
`BlogRepository` and `PluginConfigRepository`.
"""

from collections.abc import Mapping
from typing import Any, ClassVar, Protocol

from pydantic import BaseModel, ConfigDict

from platzky.models import Footer, Image, MenuItem, PageMeta


class SiteSettings(BaseModel):
    """Branding and site text for the app in one language, resolved as a single unit.

    The text fields (app name, page title and description) are already resolved for the
    requested language and are empty when nothing is configured.
    """

    model_config = ConfigDict(frozen=True)

    STORED_KEYS: ClassVar[tuple[str, ...]] = (
        "app_name",
        "app_title",
        "app_description",
        "logo_url",
        "favicon_url",
        "font",
        "primary_color",
        "secondary_color",
    )
    """The site-content keys `from_layers` reads, e.g. for a database projection."""

    logo: Image | None = None
    favicon_url: str = ""
    primary_color: str = "white"
    secondary_color: str = "navy"
    font: str = ""
    app_name: str = ""
    app_title: str = ""
    app_description: str = ""

    @classmethod
    def from_layers(
        cls, defaults: Mapping[str, Any], localized: Mapping[str, Any], lang: str
    ) -> "SiteSettings":
        """Build the site settings for a language from its defaults and overrides.

        Each text key (app_name, app_title, app_description, logo_url) is taken from
        ``localized`` if set there, else from ``defaults``, else left empty. Missing,
        null and empty values fall through to the next source. Only the keys in
        `STORED_KEYS` are read.

        ``lang`` is used only for the legacy format, where a top-level
        ``app_description`` in ``defaults`` is a ``{lang: text}`` dict.

        Args:
            defaults: The language-independent site content (JSON ``site_content``
                or the Mongo ``config`` document).
            localized: The overrides for this language (empty if there are none).
            lang: Language code (e.g., 'en', 'pl'), for the legacy description only.

        Returns:
            The site settings for that language.
        """
        stored = {key: defaults.get(key) for key in cls.STORED_KEYS}
        overrides = {key: localized.get(key) for key in cls.STORED_KEYS}
        description = stored["app_description"]
        if isinstance(description, dict):
            stored["app_description"] = description.get(lang)

        def text(key: str) -> str:
            return overrides[key] or stored[key] or ""

        logo_url = text("logo_url")
        return cls(
            logo=Image(url=logo_url) if logo_url else None,
            favicon_url=stored["favicon_url"] or "",
            primary_color=stored["primary_color"] or "white",
            secondary_color=stored["secondary_color"] or "navy",
            font=stored["font"] or "",
            app_name=text("app_name"),
            app_title=text("app_title"),
            app_description=text("app_description"),
        )


class SiteConfigRepository(Protocol):
    """Repository for site-wide branding, navigation, and home page config."""

    def get_site_settings(self, lang: str) -> SiteSettings:
        """Retrieve branding and site text for the app in a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The app's site settings, with text empty where none is configured.
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

    def get_blog_meta(self, lang: str) -> PageMeta:
        """Retrieve the blog index's title and description for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The blog meta, empty if none is configured for the language.
        """
        ...

    def get_footer(self, lang: str) -> Footer:
        """Retrieve the site-wide footer for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The footer, empty and not collapsible if none is configured.
        """
        ...
