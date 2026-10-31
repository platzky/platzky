"""SiteConfigRepository implementation backed by a GraphQL (Hygraph) CMS."""

from typing import Any, Callable

from gql import Client, gql
from typing_extensions import override

from platzky.db.site_config_repository import SiteConfigRepository, SiteSettings
from platzky.models import Footer, Image, MenuItem, PageMeta

# Relation nodes may be null in the CMS, so these helpers turn a null list, a
# null entry or a null nested node into the documented default instead of raising.


def _first(nodes: list[dict[str, Any] | None] | None) -> dict[str, Any]:
    """Return the first node of a CMS list, or an empty mapping if there is none."""
    return (nodes[0] if nodes else None) or {}


def _logo(logo: dict[str, Any] | None) -> Image | None:
    """Build the site logo from a CMS logo node, or None if it has no image."""
    logo = logo or {}
    url = (logo.get("image") or {}).get("url")
    return Image(url=url, alternateText=logo.get("alternateText") or "") if url else None


class GraphQLSiteConfigRepository(SiteConfigRepository):
    """Site config repository backed by a GraphQL CMS.

    `get_site_settings()` combines what used to be four separate queries
    (logo, favicon, theme colors, per-language app description) into one
    request -- the same round-trip reduction `MongoSiteConfigRepository` gets
    for free by fetching its whole config document in one `find_one`.
    """

    def __init__(self, client_getter: Callable[[], Client]) -> None:
        """Store the client source.

        Args:
            client_getter: Zero-argument callable returning the GraphQL client to
                use for the current thread.
        """
        self._client_getter = client_getter

    @override
    def get_site_settings(self) -> SiteSettings:
        """Retrieve branding and description settings for the app.

        Returns:
            The app's site settings.
        """
        # applicationSetups holds one entry per language. Hygraph returns only
        # 10 entries unless `first` is given (100 is the maximum per page), so
        # ask for the maximum; a site with more than 100 languages is not a
        # realistic case.
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
              applicationSetups(stage: PUBLISHED, first: 100) {
                language
                applicationDescription
              }
            }
            """)
        result = self._client_getter().execute(query)

        theme = _first(result.get("themes"))
        app_description = {
            item["language"]: item.get("applicationDescription") or ""
            for item in result.get("applicationSetups") or []
            if item
        }

        return SiteSettings(
            logo=_logo(_first(result.get("logos")).get("logo")),
            favicon_url=(_first(result.get("favicons")).get("favicon") or {}).get("url") or "",
            primary_color=theme.get("primaryColor") or "white",
            secondary_color=theme.get("secondaryColor") or "navy",
            font="",  # not implemented in GraphQL backend
            app_description=app_description,
        )

    @override
    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        """Retrieve menu items for a specific language.

        Args:
            lang: Language code (e.g., 'en', 'pl').

        Returns:
            Menu items in that language.
        """
        menu_items_query = gql("""
            query MyQuery($lang: Lang!) {
              menuItems(where: {language: $lang}, stage: PUBLISHED, first: 100){
                name
                url
              }
            }
            """)
        menu_items = self._client_getter().execute(menu_items_query, variable_values={"lang": lang})
        return [MenuItem.model_validate(item) for item in menu_items.get("menuItems") or []]

    @override
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
        result = self._client_getter().execute(
            home_page_path_query, variable_values={"lang": locale}
        )
        return _first(result.get("applicationSetups")).get("homePagePath")

    @override
    def get_blog_meta(self, lang: str) -> PageMeta:
        """Retrieve the blog index's title and description for a specific language.

        The CMS schema has no blog meta content type, so this queries nothing and the blog
        index uses its default title and the site's description.

        Args:
            lang: Language code (e.g., 'en', 'pl'), unused.

        Returns:
            An empty blog meta.
        """
        return PageMeta()

    @override
    def get_footer(self, lang: str) -> Footer:
        """Retrieve the site-wide footer for a specific language.

        The CMS schema has no footer content type, so this queries nothing and
        shows no footer.

        Args:
            lang: Language code (e.g., 'en', 'pl'), unused.

        Returns:
            An empty, non-collapsible footer.
        """
        return Footer()
