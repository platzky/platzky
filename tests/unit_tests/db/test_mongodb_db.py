from typing import cast
from unittest.mock import Mock, patch

import pytest

from platzky.db.mongodb_db import MongoDB, MongoDbConfig, db_from_config, get_db
from platzky.models import MenuItem, Post


class TestMongoDbConfig:
    def test_model_validation(self):
        config_data = {
            "TYPE": "mongodb",
            "CONNECTION_STRING": "mongodb://localhost:27017",
            "DATABASE_NAME": "test_db",
        }
        config = MongoDbConfig.model_validate(config_data)
        assert config.connection_string == "mongodb://localhost:27017"
        assert config.database_name == "test_db"


class TestFactoryFunctions:
    @patch("platzky.db.mongodb_db.MongoClient")
    def test_get_db(self, mock_client: Mock):
        config_data = {
            "TYPE": "mongodb",
            "CONNECTION_STRING": "mongodb://localhost:27017",
            "DATABASE_NAME": "test_db",
        }
        db = get_db(config_data)
        assert isinstance(db, MongoDB)
        mock_client.assert_called_once_with("mongodb://localhost:27017")

    @patch("platzky.db.mongodb_db.MongoClient")
    def test_db_from_config(self, mock_client: Mock):
        config = MongoDbConfig.model_validate(
            {
                "TYPE": "mongodb",
                "CONNECTION_STRING": "mongodb://localhost:27017",
                "DATABASE_NAME": "test_db",
            }
        )
        db = db_from_config(config)
        assert isinstance(db, MongoDB)
        mock_client.assert_called_once_with("mongodb://localhost:27017")


class TestMongoDB:
    @pytest.fixture
    def mock_client(self):
        with patch("platzky.db.mongodb_db.MongoClient") as mock_client:
            mock_db = Mock()
            mock_client.return_value.__getitem__.return_value = mock_db

            # Set up collection mocks
            mock_db.site_content = Mock()
            mock_db.posts = Mock()
            mock_db.pages = Mock()
            mock_db.menu_items = Mock()
            mock_db.plugins = Mock()

            yield mock_client, mock_db

    @pytest.fixture
    def db(self, mock_client: tuple[Mock, Mock]) -> MongoDB:
        _ = mock_client  # Acknowledge dependency on mock_client fixture
        return MongoDB("mongodb://localhost:27017", "test_db")

    def test_init(self, mock_client: tuple[Mock, Mock]):
        mock_client_instance, _ = mock_client
        db = MongoDB("mongodb://localhost:27017", "test_db")

        assert db.connection_string == "mongodb://localhost:27017"
        assert db.database_name == "test_db"
        assert db.module_name == "mongodb_db"
        assert db.db_name == "MongoDB"
        mock_client_instance.assert_called_once_with("mongodb://localhost:27017")

    def test_get_app_description(self, db: MongoDB):
        # Mock the site_content collection
        # Note: db.site_content is Collection[Any] at runtime but Mock in tests
        mock_find_one = cast(Mock, db.site_content.find_one)
        mock_find_one.return_value = {
            "_id": "config",
            "app_description": {"en": "English description", "de": "Deutsche Beschreibung"},
        }

        assert db.get_app_description("en") == "English description"
        assert db.get_app_description("de") == "Deutsche Beschreibung"
        assert db.get_app_description("fr") == ""

        mock_find_one.assert_called_with({"_id": "config"})

    def test_get_app_description_no_data(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = None
        assert db.get_app_description("en") == ""

    def test_get_all_posts(self, db: MongoDB):
        # Mock posts data
        mock_posts = [
            {
                "_id": "1",
                "title": "Post 1",
                "slug": "post-1",
                "content": "Content 1",
                "language": "en",
                "tags": ["tag1"],
                "comments": [],
                "author": "Test Author",
                "contentInMarkdown": "# Post 1",
                "excerpt": "Post excerpt",
                "coverImage": {"url": "/images/post1.jpg"},
                "date": "2023-01-01T00:00:00",
            }
        ]

        mock_find = cast(Mock, db.posts.find)
        mock_find.return_value = mock_posts

        posts = db.get_all_posts("en")

        assert len(posts) == 1
        assert isinstance(posts[0], Post)
        assert posts[0].title == "Post 1"
        mock_find.assert_called_once_with({"language": "en"})

    def test_get_menu_items_in_lang(self, db: MongoDB):
        # Mock menu items data
        mock_find_one = cast(Mock, db.menu_items.find_one)
        mock_find_one.return_value = {
            "_id": "en",
            "items": [{"name": "Home", "url": "/", "weight": 1}],
        }

        menu_items = db.get_menu_items_in_lang("en")

        assert len(menu_items) == 1
        assert isinstance(menu_items[0], MenuItem)
        assert menu_items[0].name == "Home"
        mock_find_one.assert_called_once_with({"_id": "en"})

    def test_get_menu_items_in_lang_no_data(self, db: MongoDB):
        cast(Mock, db.menu_items.find_one).return_value = None
        menu_items = db.get_menu_items_in_lang("fr")
        assert len(menu_items) == 0

    def test_get_post(self, db: MongoDB):
        # Mock post data
        mock_post = {
            "_id": "1",
            "title": "Post 1",
            "slug": "post-1",
            "content": "Content 1",
            "language": "en",
            "tags": ["tag1"],
            "comments": [],
            "author": "Test Author",
            "contentInMarkdown": "# Post 1",
            "excerpt": "Post excerpt",
            "coverImage": {"url": "/images/post1.jpg"},
            "date": "2023-01-01T00:00:00",
        }

        mock_find_one = cast(Mock, db.posts.find_one)
        mock_find_one.return_value = mock_post

        post = db.get_post("post-1")

        assert isinstance(post, Post)
        assert post.title == "Post 1"
        mock_find_one.assert_called_once_with({"slug": "post-1"})

    def test_get_post_not_found(self, db: MongoDB):
        cast(Mock, db.posts.find_one).return_value = None

        with pytest.raises(ValueError, match="Post with slug non-existent not found"):
            db.get_post("non-existent")

    def test_get_page(self, db: MongoDB):
        # Mock page data
        mock_page = {
            "_id": "1",
            "title": "Page 1",
            "slug": "page-1",
            "content": "Page content",
            "language": "en",
            "tags": [],
            "comments": [],
            "author": "Page Author",
            "contentInMarkdown": "# Page 1",
            "excerpt": "Page excerpt",
            "coverImage": {"url": "/images/page1.jpg"},
            "date": "2023-01-01T00:00:00",
        }

        mock_find_one = cast(Mock, db.pages.find_one)
        mock_find_one.return_value = mock_page

        page = db.get_page("page-1")

        assert isinstance(page, Post)  # Page is actually Post type in platzky
        assert page.title == "Page 1"
        mock_find_one.assert_called_once_with({"slug": "page-1"})

    def test_get_page_not_found(self, db: MongoDB):
        cast(Mock, db.pages.find_one).return_value = None

        with pytest.raises(ValueError, match="Page with slug non-existent not found"):
            db.get_page("non-existent")

    def test_get_posts_by_tag(self, db: MongoDB):
        mock_posts = [
            {
                "title": "Tagged Post",
                "slug": "tagged-post",
                "content": "Content",
                "language": "en",
                "tags": ["tag1"],
                "comments": [],
                "author": "Test Author",
                "contentInMarkdown": "# Tagged Post",
                "excerpt": "Excerpt",
                "coverImage": {"url": "/images/post.jpg"},
                "date": "2023-01-01T00:00:00",
            }
        ]
        mock_find = cast(Mock, db.posts.find)
        mock_find.return_value = mock_posts

        result = db.get_posts_by_tag("tag1", "en")

        assert len(result) == 1
        assert isinstance(result[0], Post)
        assert result[0].title == "Tagged Post"
        mock_find.assert_called_once_with({"tags": "tag1", "language": "en"})

    def test_add_comment(self, db: MongoDB):
        with patch("platzky.db.mongodb_db.datetime.datetime") as mock_datetime:
            test_date = Mock()
            test_date.isoformat.return_value = "2023-01-01T12:00:00"
            mock_datetime.now.return_value = test_date

            db.add_comment("Test User", "Great post!", "post-1")

            expected_comment = {
                "author": "Test User",
                "comment": "Great post!",
                "date": "2023-01-01T12:00:00",
            }

            cast(Mock, db.posts.update_one).assert_called_once_with(
                {"slug": "post-1"}, {"$push": {"comments": expected_comment}}
            )

    def test_get_logo_url(self, db: MongoDB):
        mock_find_one = cast(Mock, db.site_content.find_one)
        mock_find_one.return_value = {"_id": "config", "logo_url": "/logo.png"}

        assert db.get_logo_url() == "/logo.png"
        mock_find_one.assert_called_with({"_id": "config"})

    def test_get_logo_url_no_data(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = None
        assert db.get_logo_url() == ""

    def test_get_favicon_url(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = {
            "_id": "config",
            "favicon_url": "/favicon.ico",
        }

        assert db.get_favicon_url() == "/favicon.ico"

    def test_get_primary_color(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = {
            "_id": "config",
            "primary_color": "blue",
        }

        assert db.get_primary_color() == "blue"

    def test_get_primary_color_default(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = {"_id": "config"}

        assert db.get_primary_color() == "white"

    def test_get_secondary_color(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = {
            "_id": "config",
            "secondary_color": "green",
        }

        assert db.get_secondary_color() == "green"

    def test_get_secondary_color_default(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = None
        assert db.get_secondary_color() == "navy"

    def test_get_plugins_data(self, db: MongoDB):
        cast(Mock, db.plugins.find_one).return_value = {
            "_id": "config",
            "data": [{"name": "plugin1"}],
        }

        plugins = db.get_plugins_data()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "plugin1"

    def test_get_plugins_data_no_data(self, db: MongoDB):
        cast(Mock, db.plugins.find_one).return_value = None
        assert db.get_plugins_data() == []

    def test_get_font(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = {"_id": "config", "font": "Arial"}

        assert db.get_font() == "Arial"

    def test_get_font_default(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = None
        assert db.get_font() == ""

    def test_close_connection(self, db: MongoDB):
        db._close_connection()  # type: ignore[reportPrivateUsage] - Testing private method
        cast(Mock, db.client.close).assert_called_once()

    def test_health_check_success(self, db: MongoDB):
        """Test health check when database is accessible"""
        mock_command = cast(Mock, db.client.admin.command)
        mock_command.return_value = {"ok": 1}

        # Should not raise any exception
        db.health_check()

        mock_command.assert_called_once_with("ping")

    def test_health_check_failure(self, db: MongoDB):
        """Test health check when database is not accessible"""
        cast(Mock, db.client.admin.command).side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            db.health_check()
