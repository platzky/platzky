import datetime
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from platzky.db.json_db import Json, JsonDbConfig, db_from_config, get_db
from platzky.models import MenuItem, Page, Post


class TestJsonDbConfig:
    def test_model_validation(self):
        config_data = {
            "TYPE": "json_db",
            "DATA": {"site_content": {"app_description": {"en": "Test"}}},
        }
        config = JsonDbConfig.model_validate(config_data)
        assert config.data == {"site_content": {"app_description": {"en": "Test"}}}


class TestFactoryFunctions:
    def test_get_db(self):
        config_data = {"TYPE": "json_db", "DATA": {"test": "data"}}
        db = get_db(config_data)
        assert isinstance(db, Json)
        assert db.data == {"test": "data"}

    def test_db_from_config(self):
        config = JsonDbConfig(TYPE="json_db", DATA={"test": "data"})
        db = db_from_config(config)
        assert isinstance(db, Json)
        assert db.data == {"test": "data"}


class TestJsonDb:
    @pytest.fixture
    def sample_data(self) -> dict[str, Any]:
        return {
            "site_content": {
                "app_description": {"en": "English description", "de": "Deutsche Beschreibung"},
                "posts": [
                    {
                        "title": "Post 1",
                        "slug": "post-1",
                        "content": "Content 1",
                        "language": "en",
                        "tags": ["tag1", "tag2"],
                        "comments": [],
                        "author": "Test Author",
                        "contentInMarkdown": "# Post 1",
                        "excerpt": "Post 1 excerpt",
                        "coverImage": {"url": "/images/post1.jpg"},
                        "date": "2023-01-01T00:00:00",
                    },
                    {
                        "title": "Post 2",
                        "slug": "post-2",
                        "content": "Content 2",
                        "language": "de",
                        "tags": ["tag2", "tag3"],
                        "comments": [],
                        "author": "Test Author",
                        "contentInMarkdown": "# Post 2",
                        "excerpt": "Post 2 excerpt",
                        "coverImage": {"url": "/images/post2.jpg"},
                        "date": "2023-01-02T00:00:00",
                    },
                ],
                "pages": [
                    {
                        "title": "Page 1",
                        "slug": "page-1",
                        "content": "Page content",
                        "author": "Page Author",
                        "contentInMarkdown": "# Page 1",
                        "excerpt": "Page 1 excerpt",
                        "comments": [],
                        "tags": [],
                        "language": "en",
                        "coverImage": {"url": "/images/page1.jpg"},
                        "date": "2023-01-03T00:00:00",
                    }
                ],
                "menu_items": {
                    "en": [{"name": "Home", "url": "/", "weight": 1}],
                    "de": [{"name": "Startseite", "url": "/", "weight": 1}],
                },
                "logo_url": "/logo.png",
                "favicon_url": "/favicon.ico",
                "font": "Arial",
                "primary_color": "blue",
                "secondary_color": "green",
            },
            "plugins": [{"name": "plugin1", "config": {}}],
        }

    @pytest.fixture
    def db(self, sample_data: dict[str, Any]) -> Json:
        return Json(sample_data)

    def test_get_app_description(self, db: Json):
        assert db.get_app_description("en") == "English description"
        assert db.get_app_description("de") == "Deutsche Beschreibung"
        assert db.get_app_description("fr") == ""

    def test_get_all_posts(self, db: Json):
        posts = db.get_all_posts("en")
        assert len(posts) == 1
        assert isinstance(posts[0], Post)
        assert posts[0].title == "Post 1"
        assert posts[0].slug == "post-1"

        de_posts = db.get_all_posts("de")
        assert len(de_posts) == 1
        assert de_posts[0].title == "Post 2"

    def test_get_post(self, db: Json):
        post = db.get_post("post-1")
        assert isinstance(post, Post)
        assert post.title == "Post 1"
        assert post.slug == "post-1"

    def test_get_post_not_found(self, db: Json):
        with pytest.raises(ValueError, match="Post with slug non-existent not found"):
            db.get_post("non-existent")

    def test_get_post_missing_data(self):
        db_without_posts = Json({"site_content": {}})
        with pytest.raises(ValueError, match="Posts data is missing"):
            db_without_posts.get_post("any-slug")

    def test_get_post_with_missing_required_field(self, db: Json):
        """ValidationError raised when required field is missing."""
        db.data["site_content"]["posts"].append(
            {
                "slug": "test-post",
                "author": "Test Author",
                "contentInMarkdown": "# Test Post",
                "excerpt": "Test excerpt",
            }
        )

        with pytest.raises(ValidationError):
            db.get_post("test-post")

    def test_get_page(self, db: Json):
        page = db.get_page("page-1")
        assert isinstance(page, Post)
        assert page.title == "Page 1"
        assert page.slug == "page-1"

    def test_get_page_not_found(self, db: Json):
        with pytest.raises(ValueError, match="Page with slug non-existent not found"):
            db.get_page("non-existent")

    def test_get_page_with_minimal_fields(self):
        """Pages can be loaded with only required fields.

        Regression test for a bug where pages required all Post fields
        (comments, tags, language, date) even though they should be optional.
        """
        minimal_page_data = {
            "site_content": {
                "pages": [
                    {
                        "title": "About Us",
                        "slug": "about",
                        "author": "Site Admin",
                        "contentInMarkdown": "# About\n\nWelcome to our site.",
                        "excerpt": "Learn more about us",
                        "coverImage": {"url": "/images/about.jpg"},
                    }
                ]
            }
        }
        db = Json(minimal_page_data)
        page = db.get_page("about")

        assert isinstance(page, Page)
        assert page.title == "About Us"
        assert page.slug == "about"
        assert page.language == "en"
        assert page.comments == []
        assert page.tags == []
        assert page.date is None

    def test_get_menu_items_in_lang(self, db: Json):
        menu_items = db.get_menu_items_in_lang("en")
        assert len(menu_items) == 1
        assert isinstance(menu_items[0], MenuItem)
        assert menu_items[0].name == "Home"

        de_menu_items = db.get_menu_items_in_lang("de")
        assert len(de_menu_items) == 1
        assert de_menu_items[0].name == "Startseite"

        fr_menu_items = db.get_menu_items_in_lang("fr")
        assert len(fr_menu_items) == 0

    def test_get_posts_by_tag(self, db: Json):
        assert db.get_posts_by_tag("tag1", "en")[0].slug == "post-1"
        assert db.get_posts_by_tag("tag2", "en")[0].slug == "post-1"
        assert db.get_posts_by_tag("tag2", "de")[0].slug == "post-2"
        assert len(db.get_posts_by_tag("tag3", "en")) == 0
        assert len(db.get_posts_by_tag("non-existent", "en")) == 0
        assert len(db.get_posts_by_tag("tag1", "fr")) == 0

    def test_get_posts_by_tag_with_empty_posts(self, db: Json):
        db.data["site_content"]["posts"] = []
        posts = list(db.get_posts_by_tag("tag1", "en"))
        assert len(posts) == 0


class TestJsonDbSiteSettings:
    @pytest.fixture
    def db_with_settings(self) -> Json:
        return Json(
            {
                "site_content": {
                    "logo_url": "/logo.png",
                    "favicon_url": "/favicon.ico",
                    "font": "Arial",
                    "primary_color": "blue",
                    "secondary_color": "green",
                }
            }
        )

    @pytest.fixture
    def db_minimal(self) -> Json:
        return Json({"site_content": {}})

    def test_get_logo_url(self, db_with_settings: Json):
        assert db_with_settings.get_logo_url() == "/logo.png"

    def test_get_favicon_url(self, db_with_settings: Json):
        assert db_with_settings.get_favicon_url() == "/favicon.ico"

    def test_get_font(self, db_with_settings: Json):
        assert db_with_settings.get_font() == "Arial"

    def test_get_primary_color(self, db_with_settings: Json):
        assert db_with_settings.get_primary_color() == "blue"

    def test_get_primary_color_default(self, db_minimal: Json):
        assert db_minimal.get_primary_color() == "white"

    def test_get_secondary_color(self, db_with_settings: Json):
        assert db_with_settings.get_secondary_color() == "green"

    def test_get_secondary_color_default(self, db_minimal: Json):
        assert db_minimal.get_secondary_color() == "navy"


class TestJsonDbComments:
    @pytest.fixture
    def db(self) -> Json:
        return Json(
            {
                "site_content": {
                    "posts": [
                        {
                            "title": "Post 1",
                            "slug": "post-1",
                            "language": "en",
                            "tags": [],
                            "comments": [],
                            "author": "Test Author",
                            "contentInMarkdown": "# Post 1",
                            "excerpt": "Post 1 excerpt",
                            "date": "2023-01-01T00:00:00",
                        }
                    ]
                }
            }
        )

    def test_add_comment(self, db: Json):
        test_date = datetime.datetime(2023, 1, 1, 12, 0)

        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = test_date
            db.add_comment("Test User", "Great post!", "post-1")

        post_data = next(
            p
            for p in db._get_site_content()["posts"]  # type: ignore[reportPrivateUsage]
            if p["slug"] == "post-1"
        )
        assert len(post_data["comments"]) == 1
        comment = post_data["comments"][0]
        assert comment["author"] == "Test User"
        assert comment["comment"] == "Great post!"
        assert comment["date"] == "2023-01-01T12:00:00"

    def test_add_comment_to_nonexistent_post(self, db: Json):
        with pytest.raises(StopIteration):
            db.add_comment("Test User", "Comment", "non-existent")


class TestJsonDbPlugins:
    def test_get_plugins_data(self):
        db = Json({"plugins": [{"name": "plugin1", "config": {}}]})
        plugins = db.get_plugins_data()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "plugin1"

    def test_get_plugins_data_empty(self):
        db = Json({})
        assert db.get_plugins_data() == []


class TestJsonDbHealthCheck:
    def test_health_check_success(self):
        db = Json({"site_content": {"posts": []}})
        db.health_check()

    def test_health_check_failure_no_site_content(self):
        db = Json({"other_data": "value"})
        with pytest.raises(Exception, match="Content should not be None"):
            db.health_check()


class TestJsonDbEmptyDb:
    def test_empty_db_raises_exception_on_operations(self):
        db = Json({})

        with pytest.raises(Exception, match="Content should not be None"):
            db.get_all_posts("en")

        with pytest.raises(Exception, match="Content should not be None"):
            db.get_logo_url()

        with pytest.raises(Exception, match="Content should not be None"):
            db.get_post("any-slug")
