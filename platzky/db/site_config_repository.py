"""Protocol for site-wide configuration: branding, menu, home page, footer, and blog meta.

Every app needs branding (logo, colors, font, description), a nav menu, and a
home page regardless of whether it has a blog, so this is kept separate from
`BlogRepository` and `PluginConfigRepository`.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from platzky.db.exceptions import InvalidSiteContentError
from platzky.models import Font, Footer, Image, MenuItem, PageMeta


class LocalizedContent(BaseModel):
    """The site content that is set per language, in the one format shared by every backend.

    Unknown keys and null values are errors. Nothing here is inherited from
    another language, and only the four text keys fall back to the site-wide defaults of
    `SiteContent` (see `SiteSettings.from_layers`).

    Attributes:
        app_name: Site name; empty falls through to the site-wide default
        app_title: Site title; empty falls through to the site-wide default
        app_description: Meta description; empty falls through to the site-wide default
        logo_url: Logo image URL; empty falls through to the site-wide default
        blog_meta: The blog index's title and description
        footer: The site-wide footer
        menu_items: The navigation menu
        home_page_path: Site-relative path shown as the home page; empty for the blog index
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    app_name: str = ""
    app_title: str = ""
    app_description: str = ""
    logo_url: str = ""
    blog_meta: PageMeta = PageMeta()
    footer: Footer = Footer()
    menu_items: tuple[MenuItem, ...] = ()
    home_page_path: str = ""


class SiteContent(BaseModel):
    """The site-configuration part of the ``site_content`` section, shared by every backend.

    The texts and the logo are defaults that each language may override; the favicon, font and
    colors are global. Everything else is per language, in ``localized_content``. Unknown keys
    are an error, except ``posts`` and ``pages``: the blog repository owns and validates those
    in the same section.

    Attributes:
        app_name: Default site name
        app_title: Default site title
        app_description: Default meta description
        logo_url: Default logo image URL
        favicon_url: Favicon URL
        font: Font family name and stylesheet
        primary_color: Primary theme color
        secondary_color: Secondary theme color
        posts: Blog posts, owned by the blog repository
        pages: Pages, owned by the blog repository
        localized_content: The per-language content, by language code
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    app_name: str = ""
    app_title: str = ""
    app_description: str = ""
    logo_url: str = ""
    favicon_url: str = ""
    font: Font = Font()
    primary_color: str = ""
    secondary_color: str = ""
    posts: Any = None
    pages: Any = None
    localized_content: Mapping[str, LocalizedContent] = Field(
        default_factory=lambda: MappingProxyType({})
    )

    @field_validator("localized_content", mode="after")
    @classmethod
    def _read_only(cls, value: Mapping[str, LocalizedContent]) -> Mapping[str, LocalizedContent]:
        return MappingProxyType(dict(value))

    def localized(self, lang: str) -> LocalizedContent:
        """Return the content of a language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The language's content, empty if none is configured for it.
        """
        return self.localized_content.get(lang, LocalizedContent())


def parse_site_content(site_content: object) -> SiteContent:
    """Validate the site content as stored, e.g. when the application starts.

    Args:
        site_content: The ``site_content`` section of the database.

    Returns:
        The validated site content.

    Raises:
        InvalidSiteContentError: If it is invalid; the message lists every problem with its
            path, one per line.
    """
    try:
        return SiteContent.model_validate(site_content)
    except ValidationError as error:
        problems = (
            ".".join(["site_content", *(str(part) for part in problem["loc"])])
            + f": {problem['msg']}"
            for problem in error.errors()
        )
        raise InvalidSiteContentError("\n".join(problems)) from error


class SiteSettings(BaseModel):
    """Branding and site text for the app in one language, resolved as a single unit.

    The text fields (app name, page title and description) are already resolved for the
    requested language and are empty when nothing is configured.
    """

    model_config = ConfigDict(frozen=True)

    TEXT_KEYS: ClassVar[tuple[str, ...]] = (
        "app_name",
        "app_title",
        "app_description",
        "logo_url",
    )
    """The keys a language may override, e.g. for a database projection of its content."""

    STORED_KEYS: ClassVar[tuple[str, ...]] = (
        *TEXT_KEYS,
        "favicon_url",
        "font",
        "primary_color",
        "secondary_color",
    )
    """The site-wide keys `from_layers` reads, e.g. for a database projection."""

    logo: Image | None = None
    favicon_url: str = ""
    primary_color: str = "white"
    secondary_color: str = "navy"
    font: Font = Font()
    app_name: str = ""
    app_title: str = ""
    app_description: str = ""

    @classmethod
    def from_layers(cls, defaults: SiteContent, localized: LocalizedContent) -> "SiteSettings":
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
        logo_url = localized.logo_url or defaults.logo_url
        return cls(
            logo=Image(url=logo_url) if logo_url else None,
            favicon_url=defaults.favicon_url or "",
            primary_color=defaults.primary_color or "white",
            secondary_color=defaults.secondary_color or "navy",
            font=defaults.font,
            app_name=localized.app_name or defaults.app_name or "",
            app_title=localized.app_title or defaults.app_title or "",
            app_description=localized.app_description or defaults.app_description or "",
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
