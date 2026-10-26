"""SiteConfigRepository implementation backed by a GraphQL (Hygraph) CMS."""

from typing import Callable

from gql import Client, gql

from platzky.db.site_config_repository import SiteSettings
from platzky.models import Footer, Image, MenuItem, PageMeta


class GraphQLSiteConfigRepository:
    """Site config repository backed by a GraphQL CMS.

    `get_site_settings()` combines what used to be four separate queries
    (logo, favicon, theme colors, per-language app description) into one
    request -- the same round-trip reduction `MongoSiteConfigRepository` gets
    for free by fetching its whole config document in one `find_one`.
    """

    def __init__(self, get_client: Callable[[], Client]) -> None:
        """Store the client source.

        Args:
            get_client: Zero-argument callable returning the GraphQL client to
                use for the current thread.
        """
        self._get_client = get_client

    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        query = gql("""
            query MyQuery {
              logos(stage: PUBLISHED) {
                logo {
                  alternateText
                  image {
                    url
                  }
                }
              }
              favicons(stage: PUBLISHED) {
                favicon {
                  url
                }
              }
              themes(stage: PUBLISHED) {
                primaryColor
                secondaryColor
              }
              applicationSetups(stage: PUBLISHED) {
                language
                applicationDescription
              }
            }
            """)
        result = self._get_client().execute(query)

        # Relation nodes may be null in the CMS, so every level falls back to
        # the documented default instead of raising.
        logos = result.get("logos") or []
        logo_raw = (logos[0] or {}).get("logo") if logos else None
        logo_url = ((logo_raw or {}).get("image") or {}).get("url")
        logo = (
            Image(url=logo_url, alternateText=(logo_raw or {}).get("alternateText") or "")
            if logo_url
            else None
        )

        favicons = result.get("favicons") or []
        favicon_raw = (favicons[0] or {}).get("favicon") if favicons else None
        favicon_url = (favicon_raw or {}).get("url") or ""

        themes = result.get("themes") or []
        theme = (themes[0] or {}) if themes else {}
        primary_color = theme.get("primaryColor") or "white"
        secondary_color = theme.get("secondaryColor") or "navy"

        app_description = {
            item["language"]: item.get("applicationDescription") or ""
            for item in result.get("applicationSetups") or []
        }

        return SiteSettings(
            logo=logo,
            favicon_url=favicon_url,
            primary_color=primary_color,
            secondary_color=secondary_color,
            font="",  # not implemented in GraphQL backend
            app_description=app_description,
        )

    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Menu items in that language.
        """
        menu_items_query = gql("""
            query MyQuery($lang: Lang!) {
              menuItems(where: {language: $lang}, stage: PUBLISHED){
                name
                url
              }
            }
            """)
        menu_items = self._get_client().execute(menu_items_query, variable_values={"lang": lang})
        return [MenuItem.model_validate(item) for item in menu_items["menuItems"]]

    def get_home_page_path(self, locale: str) -> str | None:
        """Retrieve the site-relative path configured as the site's homepage.

        Each language has its own ``applicationSetups`` entry in the CMS, so the
        homepage path is looked up for the current locale's entry directly.

        Args:
            locale: Language code (e.g., 'en', 'pl') of the current request.

        Returns:
            Homepage path, or None if no homepage override is configured for
            this locale.
        """
        home_page_path_query = gql("""
            query MyQuery($lang: Lang!) {
              applicationSetups(where: {language: $lang}, stage: PUBLISHED) {
                homePagePath
              }
            }
            """)
        try:
            return (
                self._get_client()
                .execute(home_page_path_query, variable_values={"lang": locale})[
                    "applicationSetups"
                ][0]
                .get("homePagePath")
            )
        except IndexError:
            return None

    def get_blog_meta(self, lang: str) -> PageMeta:  # noqa: ARG002
        """Retrieve the blog index's title and description for a specific language.

        The CMS schema has no blog meta content type, so this queries nothing and the blog
        index uses its default title and the site's description.

        Args:
            lang: Language code (e.g., 'en', 'pl'), unused.

        Returns:
            An empty blog meta.
        """
        return PageMeta()

    def get_footer(self, lang: str) -> Footer:  # noqa: ARG002
        """Retrieve the site-wide footer for a specific language.

        The CMS schema has no footer content type, so this queries nothing and
        shows no footer.

        Args:
            lang: Language code (e.g., 'en', 'pl'), unused.

        Returns:
            An empty, non-collapsible footer.
        """
        return Footer()
