import datetime
from unittest.mock import patch

import pytest

from platzky.db.json_db import Json, JsonDbConfig, db_from_config, get_db
from platzky.models import MenuItem, Post


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
    def sample_data(self):
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
    def db(self, sample_data):
        return Json(sample_data)

    def test_get_app_description(self, db):
        assert db.get_app_description("en") == "English description"
        assert db.get_app_description("de") == "Deutsche Beschreibung"
        assert db.get_app_description("fr") is None

    def test_get_all_posts(self, db):
        posts = db.get_all_posts("en")
        assert len(posts) == 1
        assert isinstance(posts[0], Post)
        assert posts[0].title == "Post 1"
        assert posts[0].slug == "post-1"

        de_posts = db.get_all_posts("de")
        assert len(de_posts) == 1
        assert de_posts[0].title == "Post 2"

    def test_get_post(self, db):
        post = db.get_post("post-1")
        assert isinstance(post, Post)
        assert post.title == "Post 1"
        assert post.slug == "post-1"

    def test_get_post_not_found(self, db):
        with pytest.raises(ValueError, match="Post with slug non-existent not found"):
            db.get_post("non-existent")

    def test_get_post_missing_data(self, db):
        db_without_posts = Json({"site_content": {}})
        with pytest.raises(ValueError, match="Posts data is missing"):
            db_without_posts.get_post("any-slug")

    def test_get_page(self, db):
        page = db.get_page("page-1")
        assert isinstance(page, Post)
        assert page.title == "Page 1"
        assert page.slug == "page-1"

    def test_get_page_not_found(self, db):
        # FIX: db.get_page() now raises ValueError instead of StopIteration (PEP 479)
        with pytest.raises(ValueError, match="Page with slug non-existent not found"):
            db.get_page("non-existent")

    def test_get_menu_items_in_lang(self, db):
        menu_items = db.get_menu_items_in_lang("en")
        assert len(menu_items) == 1
        assert isinstance(menu_items[0], MenuItem)
        assert menu_items[0].name == "Home"

        de_menu_items = db.get_menu_items_in_lang("de")
        assert len(de_menu_items) == 1
        assert de_menu_items[0].name == "Startseite"

        fr_menu_items = db.get_menu_items_in_lang("fr")
        assert len(fr_menu_items) == 0

    def test_get_posts_by_tag(self, db):
        # Test posts with tag1 in English
        tag1_en_posts = list(db.get_posts_by_tag("tag1", "en"))
        assert len(tag1_en_posts) == 1
        assert tag1_en_posts[0]["slug"] == "post-1"

        # Test posts with tag2 in English
        tag2_en_posts = list(db.get_posts_by_tag("tag2", "en"))
        assert len(tag2_en_posts) == 1
        assert tag2_en_posts[0]["slug"] == "post-1"

        # Test posts with tag2 in German
        tag2_de_posts = list(db.get_posts_by_tag("tag2", "de"))
        assert len(tag2_de_posts) == 1
        assert tag2_de_posts[0]["slug"] == "post-2"

        # Test posts with tag3 in English (should be empty)
        tag3_en_posts = list(db.get_posts_by_tag("tag3", "en"))
        assert len(tag3_en_posts) == 0

        # Test posts with non-existent tag
        non_existent_posts = list(db.get_posts_by_tag("non-existent", "en"))
        assert len(non_existent_posts) == 0

        # Test posts with valid tag but non-existent language
        tag1_fr_posts = list(db.get_posts_by_tag("tag1", "fr"))
        assert len(tag1_fr_posts) == 0

    def test_empty_db_raises_exception_on_operations(self):
        db = Json({})
        # Test through public methods that rely on _get_site_content() internally
        with pytest.raises(Exception, match="Content should not be None"):
            db.get_all_posts("en")

        with pytest.raises(Exception, match="Content should not be None"):
            db.get_logo_url()

        with pytest.raises(Exception, match="Content should not be None"):
            db.get_post("any-slug")

    def test_get_logo_url(self, db):
        assert db.get_logo_url() == "/logo.png"

    def test_get_favicon_url(self, db):
        assert db.get_favicon_url() == "/favicon.ico"

    def test_get_font(self, db):
        assert db.get_font() == "Arial"

    def test_get_primary_color(self, db):
        assert db.get_primary_color() == "blue"

    def test_get_primary_color_default(self):
        db = Json({"site_content": {}})
        assert db.get_primary_color() == "white"

    def test_get_secondary_color(self, db):
        assert db.get_secondary_color() == "green"

    def test_get_secondary_color_default(self):
        db = Json({"site_content": {}})
        assert db.get_secondary_color() == "navy"

    def test_add_comment(self, db):
        # Create a real datetime object for the test
        test_date = datetime.datetime(2023, 1, 1, 12, 0)

        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = test_date
            db.add_comment("Test User", "Great post!", "post-1")

        # Instead of using get_post which has validation issues, directly check the data
        post_data = next(p for p in db._get_site_content()["posts"] if p["slug"] == "post-1")
        assert len(post_data["comments"]) == 1
        comment = post_data["comments"][0]
        assert comment["author"] == "Test User"
        assert comment["comment"] == "Great post!"
        assert comment["date"] == "2023-01-01T12:00:00"

    def test_add_comment_to_nonexistent_post(self, db):
        with pytest.raises(StopIteration):
            db.add_comment("Test User", "Comment", "non-existent")

    def test_get_plugins_data(self, db):
        plugins = db.get_plugins_data()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "plugin1"

    def test_get_plugins_data_empty(self):
        db = Json({})
        assert db.get_plugins_data() == []

    def test_get_post_with_missing_data(self, db):
        """Test that get_post raises ValueError when post data is missing."""
        # Create a post with missing required data
        post = {
            "title": "Test Post",
            "slug": "test-post",
            "language": "en",
            "tags": ["tag1"],
            "comments": [],
            "author": "Test Author",
            "contentInMarkdown": "# Test Post",
            "excerpt": "Test excerpt",
            "date": "2023-01-01T00:00:00",
        }

        # Add the post to the database
        db.data["site_content"]["posts"].append(post)

        # Test that get_post raises ValueError when required data is missing
        with pytest.raises(ValueError):
            db.get_post("test-post")

    def test_get_posts_by_tag_with_empty_posts(self, db):
        """Test that get_posts_by_tag returns empty generator when posts list is empty."""
        # Clear the posts list
        db.data["site_content"]["posts"] = []

        # Test that get_posts_by_tag returns empty generator
        posts = list(db.get_posts_by_tag("tag1", "en"))
        assert len(posts) == 0

    def test_get_primary_color_with_missing_data(self, db):
        """Test that get_primary_color returns default value when data is missing."""
        # Remove primary_color from site_content
        del db.data["site_content"]["primary_color"]

        # Test that get_primary_color returns default value
        assert db.get_primary_color() == "white"

    def test_get_secondary_color_with_missing_data(self, db):
        """Test that get_secondary_color returns default value when data is missing."""
        # Remove secondary_color from site_content
        del db.data["site_content"]["secondary_color"]

        # Test that get_secondary_color returns default value
        assert db.get_secondary_color() == "navy"

    def test_add_comment_with_invalid_post(self, db):
        """Test that add_comment raises StopIteration when post is invalid."""
        # Create a post with invalid slug
        post = {
            "title": "Test Post",
            "slug": None,  # Invalid slug
            "language": "en",
            "tags": ["tag1"],
            "comments": [],
            "author": "Test Author",
            "contentInMarkdown": "# Test Post",
            "excerpt": "Test excerpt",
            "date": "2023-01-01T00:00:00",
        }

        # Add the post to the database
        db.data["site_content"]["posts"].append(post)

        # Test that add_comment raises StopIteration when post is invalid
        with pytest.raises(StopIteration):
            db.add_comment("Test Author", "Test Comment", "test-post")

    def test_health_check_success(self, db):
        """Test health check when database is accessible"""
        # Should not raise any exception
        db.health_check()

    def test_health_check_failure_no_site_content(self):
        """Test health check when site_content is missing"""
        db_no_content = Json({"other_data": "value"})

        with pytest.raises(Exception, match="Content should not be None"):
            db_no_content.health_check()
