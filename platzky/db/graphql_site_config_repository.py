"""SiteConfigRepository implementation backed by a GraphQL (Hygraph) CMS."""

from gql import gql

from platzky.db.graphql_client import make_lazy_graphql_client
from platzky.db.site_config_repository import SiteSettings
from platzky.models import Image, MenuItem


class GraphQLSiteConfigRepository:
    """Site config repository backed by a GraphQL CMS.

    `get_site_settings()` combines what used to be four separate queries
    (logo, favicon, theme colors, per-language app description) into one
    request -- the same round-trip reduction `MongoSiteConfigRepository` gets
    for free by fetching its whole config document in one `find_one`.
    """

    def __init__(self, endpoint: str, token: str) -> None:
        """Store connection details for a lazily-built, per-thread client.

        Args:
            endpoint: GraphQL API endpoint URL.
            token: Authentication token for the API.
        """
        self._get_client = make_lazy_graphql_client(endpoint, token)

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

        try:
            logo_raw = result["logos"][0]["logo"]
            logo_url = logo_raw["image"]["url"]
            logo = (
                Image(url=logo_url, alternateText=logo_raw.get("alternateText") or "")
                if logo_url
                else None
            )
        except IndexError:
            logo = None

        try:
            favicon_url = result["favicons"][0]["favicon"]["url"]
        except IndexError:
            favicon_url = ""

        try:
            theme = result["themes"][0]
            primary_color = theme.get("primaryColor") or "white"
            secondary_color = theme.get("secondaryColor") or "navy"
        except IndexError:
            primary_color = "white"
            secondary_color = "navy"

        app_description = {
            item["language"]: item.get("applicationDescription", "")
            for item in result.get("applicationSetups", [])
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
