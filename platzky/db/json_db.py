import datetime
from typing import Any, Dict

from pydantic import Field

from platzky.db.db import DB, DBConfig
from platzky.models import MenuItem, Post


def db_config_type():
    return JsonDbConfig


class JsonDbConfig(DBConfig):
    data: Dict[str, Any] = Field(alias="DATA")


def get_db(config):
    json_db_config = JsonDbConfig.model_validate(config)
    return Json(json_db_config.data)


def db_from_config(config: JsonDbConfig):
    return Json(config.data)


# TODO make all language specific methods to be available without language
# this will allow to have a default language and if there is one language
# there will be no need to pass it to the method or in db


class Json(DB):
    def __init__(self, data: Dict[str, Any]):
        super().__init__()
        self.data: Dict[str, Any] = data
        self.module_name = "json_db"
        self.db_name = "JsonDb"

    def get_app_description(self, lang):
        description = self._get_site_content().get("app_description", {})
        return description.get(lang, None)

    def get_all_posts(self, lang):
        return [
            Post.model_validate(post)
            for post in self._get_site_content().get("posts", ())
            if post["language"] == lang
        ]

    def get_post(self, slug: str) -> Post:
        """Returns a post matching the given slug."""
        all_posts = self._get_site_content().get("posts")
        if all_posts is None:
            raise ValueError("Posts data is missing")
        wanted_post = next((post for post in all_posts if post["slug"] == slug), None)
        if wanted_post is None:
            raise ValueError(f"Post with slug {slug} not found")
        return Post.model_validate(wanted_post)

    # TODO: add test for non-existing page
    def get_page(self, slug):
        list_of_pages = (
            page for page in self._get_site_content().get("pages") if page["slug"] == slug
        )
        page = Post.model_validate(next(list_of_pages))
        return page

    def get_menu_items_in_lang(self, lang) -> list[MenuItem]:
        menu_items_raw = self._get_site_content().get("menu_items", {})
        items_in_lang = menu_items_raw.get(lang, {})

        menu_items_list = [MenuItem.model_validate(x) for x in items_in_lang]
        return menu_items_list

    def get_posts_by_tag(self, tag, lang):
        return (
            post
            for post in self._get_site_content()["posts"]
            if tag in post["tags"] and post["language"] == lang
        )

    def _get_site_content(self):
        content = self.data.get("site_content")
        if content is None:
            raise Exception("Content should not be None")
        return content

    def get_logo_url(self):
        return self._get_site_content().get("logo_url", "")

    def get_favicon_url(self):
        return self._get_site_content().get("favicon_url", "")

    def get_font(self) -> str:
        return self._get_site_content().get("font", "")

    def get_primary_color(self):
        return self._get_site_content().get("primary_color", "white")

    def get_secondary_color(self):
        return self._get_site_content().get("secondary_color", "navy")

    def add_comment(self, author_name, comment, post_slug):
        # Store dates in UTC with timezone info for consistency with MongoDB backend
        # This ensures accurate time delta calculations regardless of server timezone
        # Legacy dates without timezone info are still supported for backward compatibility
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

        comment = {
            "author": str(author_name),
            "comment": str(comment),
            "date": now_utc,
        }

        post_index = next(
            i
            for i in range(len(self._get_site_content()["posts"]))
            if self._get_site_content()["posts"][i]["slug"] == post_slug
        )
        self._get_site_content()["posts"][post_index]["comments"].append(comment)

    def get_plugins_data(self):
        return self.data.get("plugins", [])

    def health_check(self) -> None:
        """Perform a health check on the JSON database.

        Raises an exception if the database is not accessible.
        """
        # Try to access site_content to ensure basic structure is valid
        self._get_site_content()
