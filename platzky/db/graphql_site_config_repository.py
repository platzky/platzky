"""SiteConfigRepository implementation backed by a GraphQL (Hygraph) CMS."""

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from gql import Client, gql
from typing_extensions import override

from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfigRepository,
    SiteContent,
    SiteSettings,
)
from platzky.models import Footer, MenuItem, PageMeta

# Relation nodes may be null in the CMS, so these helpers turn a null list, a
# null entry or a null nested node into the documented default instead of raising.


def _first(nodes: Sequence[Mapping[str, Any] | None] | None) -> Mapping[str, Any]:
    """Return the first node of a CMS list, or an empty mapping if there is none."""
    return (nodes[0] if nodes else None) or {}


def _entry(
    entries: Sequence[Mapping[str, Any] | None] | None, language: str | None
) -> Mapping[str, Any]:
    """Pick the `LocalizedContent` entry of a language.

    Args:
        entries: The `localizedContents` answer.
        language: The language code, or None for the entry holding the defaults.

    Returns:
        The matching entry, or an empty mapping if there is none.
    """
    return next((e for e in entries or [] if e and e.get("language") == language), {})


def _present(values: Mapping[str, Any]) -> dict[str, Any]:
    """Drop the null and empty values, so they fall through to the next source.

    Hygraph answers null for every field an editor left unset, so here null means "not set";
    it is not a validation of the site content.
    """
    return {key: value for key, value in values.items() if value}


def _logo_url(logo: Mapping[str, Any] | None) -> str | None:
    """Return the image URL of a CMS logo node, or None if it has no image."""
    return ((logo or {}).get("image") or {}).get("url")


def _localized_content(entry: Mapping[str, Any]) -> LocalizedContent:
    """Map the fields of a `LocalizedContent` CMS entry that it has to the shared model.

    Args:
        entry: The CMS entry, with any of its fields selected.

    Returns:
        The entry's content; null and missing fields are not set.
    """
    return LocalizedContent.model_validate(
        {
            **_present(
                {
                    "app_name": entry.get("appName"),
                    "app_title": entry.get("appTitle"),
                    "app_description": entry.get("appDescription"),
                    "logo_url": _logo_url(entry.get("logo")),
                    "home_page_path": entry.get("homePagePath"),
                }
            ),
            "blog_meta": _present(entry.get("blogMeta") or {}),
            "footer": _present(entry.get("footer") or {}),
            "menu_items": [item for item in entry.get("menuItems") or [] if item],
        }
    )


_LOCALIZED_CONTENTS = """
      localizedContents(stage: PUBLISHED, first: 100) {
        language
        appName
        appTitle
        appDescription
        logo { image { url } }
        homePagePath
        blogMeta { title description }
        footer { content collapsible }
        menuItems { name url }
      }
"""

_LOCALIZED_CONTENTS_QUERY = "query MyQuery {" + _LOCALIZED_CONTENTS + "}"

_SITE_SETTINGS_QUERY = "query MyQuery {" + _LOCALIZED_CONTENTS + """
      logos(stage: PUBLISHED) { logo { image { url } } }
      favicons(stage: PUBLISHED) { favicon { url } }
      themes(stage: PUBLISHED) {
        primaryColor
        secondaryColor
        font { name url }
      }
    }
    """


class GraphQLSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by a GraphQL CMS.

    Per-language content lives in the `LocalizedContent` model: the entry without a
    language holds the defaults and an entry with a language overrides them. Each
    method makes one request and picks the entry in Python, so the selection rules
    are the same as for the other backends. `get_site_settings()` also reads the
    language-independent logo, favicon and theme in the same request.
    """

    def __init__(self, client_getter: Callable[[], Client]) -> None:
        """Store the client source.

        Args:
            client_getter: Zero-argument callable returning the GraphQL client to
                use for the current thread.
        """
        self._client_getter = client_getter

    def _content(self, lang: str) -> LocalizedContent:
        """Fetch the `LocalizedContent` entry of a language."""
        result = self._client_getter().execute(gql(_LOCALIZED_CONTENTS_QUERY))
        return _localized_content(_entry(result.get("localizedContents"), lang))

    @override
    def get_site_settings(self, lang: str) -> SiteSettings:
        """Retrieve branding and site text for the app in a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The app's site settings, with text empty where none is configured.
        """
        result = self._client_getter().execute(gql(_SITE_SETTINGS_QUERY))
        entries = result.get("localizedContents")
        theme = _first(result.get("themes"))
        defaults = _localized_content(_entry(entries, None))
        site_content = SiteContent.model_validate(
            {
                "app_name": defaults.app_name,
                "app_title": defaults.app_title,
                "app_description": defaults.app_description,
                **_present(
                    {
                        "logo_url": defaults.logo_url
                        or _logo_url(_first(result.get("logos")).get("logo")),
                        "favicon_url": (_first(result.get("favicons")).get("favicon") or {}).get(
                            "url"
                        ),
                        "primary_color": theme.get("primaryColor"),
                        "secondary_color": theme.get("secondaryColor"),
                        "font": _present(theme.get("font") or {}),
                    }
                ),
            }
        )
        return SiteSettings.from_layers(site_content, _localized_content(_entry(entries, lang)))

    @override
    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Menu items in that language.
        """
        return list(self._content(lang).menu_items)

    @override
    def get_home_page_path(self, locale: str) -> str | None:
        """Retrieve the site-relative path configured as the site's homepage.

        Args:
            locale: Language code (e.g., 'en', 'pl') of the current request.

        Returns:
            Homepage path, or None if no homepage override is configured for
            this locale.
        """
        return self._content(locale).home_page_path or None

    @override
    def get_blog_meta(self, lang: str) -> PageMeta:
        """Retrieve the blog index's title and description for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The blog meta, empty if none is configured for the language.
        """
        return self._content(lang).blog_meta

    @override
    def get_footer(self, lang: str) -> Footer:
        """Retrieve the site-wide footer for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            The footer, empty and not collapsible if none is configured.
        """
        return self._content(lang).footer
