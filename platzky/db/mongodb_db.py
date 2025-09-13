import datetime
from typing import Any

from pydantic import Field
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from platzky.db.db import DB, DBConfig
from platzky.models import MenuItem, Page, Post


def db_config_type():
    return MongoDbConfig


class MongoDbConfig(DBConfig):
    connection_string: str = Field(alias="CONNECTION_STRING")
    database_name: str = Field(alias="DATABASE_NAME")


def get_db(config):
    mongodb_config = MongoDbConfig.model_validate(config)
    return MongoDB(mongodb_config.connection_string, mongodb_config.database_name)


def db_from_config(config: MongoDbConfig):
    return MongoDB(config.connection_string, config.database_name)


class MongoDB(DB):
    def __init__(self, connection_string: str, database_name: str):
        super().__init__()
        self.connection_string = connection_string
        self.database_name = database_name
        self.client: MongoClient[Any] = MongoClient(connection_string)
        self.db: Database[Any] = self.client[database_name]
        self.module_name = "mongodb_db"
        self.db_name = "MongoDB"

        # Collection references
        self.site_content: Collection[Any] = self.db.site_content
        self.posts: Collection[Any] = self.db.posts
        self.pages: Collection[Any] = self.db.pages
        self.menu_items: Collection[Any] = self.db.menu_items
        self.plugins: Collection[Any] = self.db.plugins

    def get_app_description(self, lang: str) -> str:
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content and "app_description" in site_content:
            return site_content["app_description"].get(lang, "")
        return ""

    def get_all_posts(self, lang: str) -> list[Post]:
        posts_cursor = self.posts.find({"language": lang})
        return [Post.model_validate(post) for post in posts_cursor]

    def get_menu_items_in_lang(self, lang: str) -> list[MenuItem]:
        menu_items_doc = self.menu_items.find_one({"_id": lang})
        if menu_items_doc and "items" in menu_items_doc:
            return [MenuItem.model_validate(item) for item in menu_items_doc["items"]]
        return []

    def get_post(self, slug: str) -> Post:
        post_doc = self.posts.find_one({"slug": slug})
        if post_doc is None:
            raise ValueError(f"Post with slug {slug} not found")
        return Post.model_validate(post_doc)

    def get_page(self, slug: str) -> Page:
        page_doc = self.pages.find_one({"slug": slug})
        if page_doc is None:
            raise ValueError(f"Page with slug {slug} not found")
        return Page.model_validate(page_doc)

    def get_posts_by_tag(self, tag: str, lang: str) -> Any:
        posts_cursor = self.posts.find({"tags": tag, "language": lang})
        return posts_cursor

    def add_comment(self, author_name: str, comment: str, post_slug: str) -> None:
        comment_doc = {
            "author": str(author_name),
            "comment": str(comment),
            "date": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }

        self.posts.update_one({"slug": post_slug}, {"$push": {"comments": comment_doc}})

    def get_logo_url(self) -> str:
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content:
            return site_content.get("logo_url", "")
        return ""

    def get_favicon_url(self) -> str:
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content:
            return site_content.get("favicon_url", "")
        return ""

    def get_primary_color(self) -> str:
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content:
            return site_content.get("primary_color", "white")
        return "white"

    def get_secondary_color(self) -> str:
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content:
            return site_content.get("secondary_color", "navy")
        return "navy"

    def get_plugins_data(self) -> list[Any]:
        plugins_doc = self.plugins.find_one({"_id": "config"})
        if plugins_doc and "data" in plugins_doc:
            return plugins_doc["data"]
        return []

    def get_font(self) -> str:
        site_content = self.site_content.find_one({"_id": "config"})
        if site_content:
            return site_content.get("font", "")
        return ""

    def _close_connection(self) -> None:
        """Close the MongoDB connection"""
        if self.client:
            self.client.close()

    def __del__(self):
        """Ensure connection is closed when object is destroyed"""
        self._close_connection()
