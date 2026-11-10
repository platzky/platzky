import datetime
from datetime import timezone
from typing import Any
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from platzky.db.exceptions import (
    DBError,
    InvalidSiteContentError,
    NotFoundError,
    ReadOnlyStorageError,
)
from platzky.db.json_db import Json, JsonDbConfig, db_from_config
from platzky.db.json_stores import JsonStore, MemoryStore, ReadOnlyStore
from platzky.models import Page


class TestJsonDbConfig:
    def test_model_validation(self):
        config_data = {
            "TYPE": "json_db",
            "DATA": {"site_content": {"app_description": "Test"}},
        }
        config = JsonDbConfig.model_validate(config_data)
        assert config.data == {"site_content": {"app_description": "Test"}}


class TestFactoryFunctions:
    def test_db_from_config(self):
        config = JsonDbConfig(
            TYPE="json_db", DATA={"site_content": {"app_description": "Configured"}}
        )
        db = db_from_config(config)
        assert isinstance(db, Json)
        assert db.site_config.get_site_content().app_description == "Configured"


class TestJsonDb:
    @pytest.fixture
    def sample_data(self) -> dict[str, Any]:
        return {
            "site_content": {
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
        db_without_posts = Json(MemoryStore({"site_content": {}}))
        with pytest.raises(NotFoundError, match="Posts data is missing"):
            db_without_posts.blog.posts.get("any-slug")

    def test_get_post_with_missing_required_field(self, sample_data: dict[str, Any]):
        """ValidationError raised when required field is missing."""
        sample_data["site_content"]["posts"].append(
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
        sample_data["site_content"]["posts"] = []
        db = Json(MemoryStore(sample_data))
        posts = list(db.blog.posts.get_by_tag("tag1", "en"))
        assert len(posts) == 0


class TestJsonDbComments:
    @pytest.fixture
    def db(self) -> Json:
        return Json(
            MemoryStore(
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

    def test_add_comment_persists_to_store(self):
        document: dict[str, Any] = {
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
        store = Mock(spec=JsonStore)
        store.load.return_value = document
        db = Json(store)
        test_date = datetime.datetime(2023, 1, 1, 12, 0)

        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = test_date
            db.blog.posts.add_comment("Test User", "Great post!", "post-1")

        store.save.assert_called_once()
        saved = store.save.call_args.args[0]
        assert saved["site_content"]["posts"][0]["comments"] == [
            {"author": "Test User", "comment": "Great post!", "date": "2023-01-01T12:00:00"}
        ]

    def test_add_comment_to_nonexistent_post(self, db: Json):
        with pytest.raises(NotFoundError, match="Post with slug non-existent not found"):
            db.blog.posts.add_comment("Test User", "Comment", "non-existent")

    def test_add_comment_rolls_back_and_logs_on_save_failure(
        self, caplog: pytest.LogCaptureFixture
    ):
        db = Json(
            ReadOnlyStore(
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
        )

        with (
            caplog.at_level("ERROR"),
            pytest.raises(ReadOnlyStorageError),
        ):
            db.blog.posts.add_comment("Test User", "Comment", "post-1")

        # The in-memory mutation is rolled back, not left dangling.
        assert db.blog.posts.get("post-1").comments == []
        assert "Failed to persist comment for post 'post-1'" in caplog.text


class TestJsonDbHealthCheck:
    def test_health_check_success(self):
        db = Json(MemoryStore({"site_content": {"posts": []}}))
        db.health_check()

    def test_health_check_failure_no_site_content(self):
        db = Json(MemoryStore({"other_data": "value"}))
        with pytest.raises(DBError, match="site_content section is missing"):
            db.health_check()


class TestJsonDbEmptyDb:
    def test_empty_db_raises_exception_on_operations(self):
        db = Json(MemoryStore({}))

        with pytest.raises(DBError, match="site_content section is missing"):
            db.blog.posts.get_all("en")

        with pytest.raises(DBError, match="site_content section is missing"):
            db.site_config.get_site_content()

        with pytest.raises(DBError, match="site_content section is missing"):
            db.blog.posts.get("any-slug")


class TestJsonDbSiteContentValidation:
    def test_health_check_reports_invalid_site_content(self):
        db = Json(MemoryStore({"site_content": {}}))
        with db.document.edit() as data:
            data["site_content"]["menu_items"] = {}

        with pytest.raises(InvalidSiteContentError):
            db.health_check()

    def test_health_check_reports_invalid_blog_meta(self):
        db = Json(MemoryStore({"site_content": {}}))
        with db.document.edit() as data:
            data["site_content"]["blog_meta"] = {"en": {"title": None}}

        with pytest.raises(InvalidSiteContentError):
            db.health_check()

    def test_invalid_blog_meta_stops_the_database_from_being_created(self):
        with pytest.raises(InvalidSiteContentError):
            Json(MemoryStore({"site_content": {"blog_meta": None}}))
