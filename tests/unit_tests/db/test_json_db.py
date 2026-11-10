import datetime
from datetime import timezone
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from platzky.db.exceptions import (
    InvalidDataError,
    NotFoundError,
)
from platzky.db.json_db import Json, JsonDbConfig, db_from_config
from platzky.db.json_stores import MemoryStore
from platzky.db.site_config_repository import LocalizedContent, SiteConfig
from platzky.models import Page


class TestJsonDbConfig:
    def test_model_validation(self):
        config_data = {
            "TYPE": "json_db",
            "DATA": {"site_config": {"app_description": "Test"}},
        }
        config = JsonDbConfig.model_validate(config_data)
        assert config.data == {"site_config": {"app_description": "Test"}}


class TestFactoryFunctions:
    def test_db_from_config(self):
        config = JsonDbConfig(
            TYPE="json_db", DATA={"site_config": {"app_description": "Configured"}}
        )
        db = db_from_config(config)
        assert isinstance(db, Json)
        assert db.site_config.get_site_config().app_description == "Configured"


class TestJsonDb:
    @pytest.fixture
    def sample_data(self) -> dict[str, Any]:
        return {
            "site_config": {},
            "blog": {
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
            },
            "plugins": {"plugin1": {"config": {}}},
        }

    @pytest.fixture
    def db(self, sample_data: dict[str, Any]) -> Json:
        return Json(MemoryStore(sample_data))

    def test_get_post_missing_data(self):
        db_without_posts = Json(MemoryStore({"site_config": {}}))
        with pytest.raises(NotFoundError, match="Post with slug any-slug not found"):
            db_without_posts.blog.posts.get("any-slug")

    def test_get_post_with_missing_required_field(self, sample_data: dict[str, Any]):
        """ValidationError raised when required field is missing."""
        sample_data["blog"]["posts"].append(
            {
                "slug": "test-post",
                "author": "Test Author",
                "contentInMarkdown": "# Test Post",
                "excerpt": "Test excerpt",
            }
        )
        db = Json(MemoryStore(sample_data))

        with pytest.raises(ValidationError):
            db.blog.posts.get("test-post")

    def test_get_page_with_minimal_fields(self):
        """Pages can be loaded with only required fields.

        Regression test for a bug where pages required all Post fields
        (comments, tags, language, date) even though they should be optional.
        """
        minimal_page_data = {
            "site_config": {},
            "blog": {
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
            },
        }
        db = Json(MemoryStore(minimal_page_data))
        page = db.blog.pages.get("about")

        assert isinstance(page, Page)
        assert page.title == "About Us"
        assert page.slug == "about"
        assert page.language == "en"
        assert page.comments == []
        assert page.tags == []
        assert page.date is None

    def test_get_posts_by_tag_with_empty_posts(self, sample_data: dict[str, Any]):
        sample_data["blog"]["posts"] = []
        db = Json(MemoryStore(sample_data))
        posts = list(db.blog.posts.get_by_tag("tag1", "en"))
        assert len(posts) == 0


class TestJsonDbComments:
    @pytest.fixture
    def db(self) -> Json:
        return Json(
            MemoryStore(
                {
                    "site_config": {},
                    "blog": {
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
                    },
                }
            )
        )

    def test_add_comment(self, db: Json):
        test_date = datetime.datetime(2023, 1, 1, 12, 0)

        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = test_date
            db.blog.posts.add_comment("Test User", "Great post!", "post-1")

        comments = db.blog.posts.get("post-1").comments
        assert len(comments) == 1
        assert comments[0].author == "Test User"
        assert comments[0].comment == "Great post!"
        assert comments[0].date == test_date.replace(tzinfo=timezone.utc)


class TestJsonDbHealthCheck:
    def test_health_check_success(self):
        db = Json(MemoryStore({"site_config": {}, "blog": {"posts": []}}))
        db.health_check()

    def test_health_check_succeeds_without_sections(self):
        Json(MemoryStore({"other_data": "value"})).health_check()


class TestJsonDbEmptyDb:
    def test_missing_site_config_section_is_the_defaults(self):
        db = Json(MemoryStore({}))

        assert db.site_config.get_site_config() == SiteConfig()
        assert db.site_config.get_localized_content("en") == LocalizedContent()

    def test_missing_blog_section_is_an_empty_blog(self):
        db = Json(MemoryStore({}))

        assert db.blog.posts.get_all("en") == []
        assert db.blog.pages.get_all("en") == []
        with pytest.raises(NotFoundError, match="Post with slug any-slug not found"):
            db.blog.posts.get("any-slug")


class TestJsonDbValidation:
    def test_creation_reports_a_site_config_problem_and_a_blog_problem_together(self):
        with pytest.raises(InvalidDataError) as error:
            Json(MemoryStore({"site_config": {"menu_items": {}}, "blog": {"posts": None}}))

        assert "site_config.menu_items" in str(error.value)
        assert "blog.posts" in str(error.value)

    def test_health_check_reports_a_problem_introduced_after_startup(self):
        db = Json(MemoryStore({"site_config": {}}))
        with db.document.edit() as data:
            data["site_config"]["menu_items"] = {}

        with pytest.raises(InvalidDataError, match=r"site_config\.menu_items"):
            db.health_check()
