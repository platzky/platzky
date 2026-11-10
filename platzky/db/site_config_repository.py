"""Protocol for site configuration: site-wide branding and per-language content.

Every app needs branding (logo, colors, font, description), a nav menu, and a
home page regardless of whether it has a blog, so this is kept separate from
`BlogRepository` and `PluginConfigRepository`.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from platzky.models import Font, Footer, MenuItem, StrictModel


class LocalizedContent(StrictModel):
    """The site content that is set per language, in the one format shared by every backend.

    Unknown keys and null values are errors. Nothing here is inherited from
    another language, and only the four text keys fall back to the site-wide defaults of
    `SiteConfig` (see `SiteSettings.from_layers`).

    Attributes:
        app_name: Site name; empty falls through to the site-wide default
        app_title: Site title; empty falls through to the site-wide default
        app_description: Meta description; empty falls through to the site-wide default
        logo_url: Logo image URL; empty falls through to the site-wide default
        footer: The site-wide footer
        menu_items: The navigation menu
        home_page_path: Site-relative path shown as the home page; empty for the blog index
    """

    app_name: str = ""
    app_title: str = ""
    app_description: str = ""
    logo_url: str = ""
    footer: Footer = Footer()
    menu_items: tuple[MenuItem, ...] = ()
    home_page_path: str = ""


DEFAULT_PRIMARY_COLOR = "white"
DEFAULT_SECONDARY_COLOR = "navy"


class SiteConfig(StrictModel):
    """The site-wide content, shared by every backend.

    The texts and the logo are defaults that each language may override; the favicon, font and
    colors are global. Everything else is per language, in `LocalizedContent`.

    Attributes:
        app_name: Default site name
        app_title: Default site title
        app_description: Default meta description
        logo_url: Default logo image URL
        favicon_url: Favicon URL
        font: Font family name and stylesheet
        primary_color: Primary theme color
        secondary_color: Secondary theme color
    """

    app_name: str = ""
    app_title: str = ""
    app_description: str = ""
    logo_url: str = ""
    favicon_url: str = ""
    font: Font = Font()
    primary_color: str = Field(default=DEFAULT_PRIMARY_COLOR, min_length=1)
    secondary_color: str = Field(default=DEFAULT_SECONDARY_COLOR, min_length=1)


class SiteSettings(BaseModel):
    """Branding and site text for the app in one language, resolved as a single unit.

    The text fields (app name, page title and description) are already resolved for the
    requested language and are empty when nothing is configured.
    """

    model_config = ConfigDict(frozen=True)

    logo_url: str = ""
    favicon_url: str = ""
    primary_color: str = DEFAULT_PRIMARY_COLOR
    secondary_color: str = DEFAULT_SECONDARY_COLOR
    font: Font = Font()
    app_name: str = ""
    app_title: str = ""
    app_description: str = ""

    @classmethod
    def from_layers(cls, defaults: SiteConfig, localized: LocalizedContent) -> "SiteSettings":
        """Build the site settings for a language from its defaults and overrides.

        Each text key (app_name, app_title, app_description, logo_url) is taken from
        ``localized`` if set there, else from ``defaults``, else left empty. Empty
        values fall through to the next source. The favicon, font and colors come from
        ``defaults`` only.

        Args:
            defaults: The site-wide content.
            localized: The overrides for this language.

        Returns:
            The site settings for that language.
        """
        return cls(
            logo_url=localized.logo_url or defaults.logo_url,
            favicon_url=defaults.favicon_url,
            primary_color=defaults.primary_color,
            secondary_color=defaults.secondary_color,
            font=defaults.font,
            app_name=localized.app_name or defaults.app_name,
            app_title=localized.app_title or defaults.app_title,
            app_description=localized.app_description or defaults.app_description,
        )


class SiteConfigRepository(Protocol):
    """Repository for the site-wide and per-language site content."""

    def get_site_config(self) -> SiteConfig:
        """Retrieve the site-wide content: texts and logo defaults, favicon, colors and font.

        Returns:
            The site-wide content, with defaults where none is configured.
        """
        ...

    def get_localized_content(self, lang: str) -> LocalizedContent:
        """Retrieve the content of one language: menu, footer, home page, texts.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The language's content, empty if none is configured for it.
        """
        ...
