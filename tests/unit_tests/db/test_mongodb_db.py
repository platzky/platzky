from typing import cast
from unittest.mock import Mock, patch

import pytest

from platzky.db.mongodb_db import MongoDB, MongoDbConfig, db_from_config
from platzky.models import Footer, MenuItem, PageMeta


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
    def db(self, mock_client: tuple[Mock, Mock]) -> MongoDB:  # noqa: ARG002
        """Create a MongoDB instance for testing.

        The mock_client fixture is required to be set up before creating the MongoDB instance.
        """
        return MongoDB("mongodb://localhost:27017", "test_db")

    def test_init(self, mock_client: tuple[Mock, Mock]):
        mock_client_instance, _ = mock_client
        db = MongoDB("mongodb://localhost:27017", "test_db")

        assert db.connection_string == "mongodb://localhost:27017"
        assert db.database_name == "test_db"
        assert db.module_name == "mongodb_db"
        assert db.db_name == "MongoDB"
        mock_client_instance.assert_called_once_with("mongodb://localhost:27017")

    def test_get_site_settings(self, db: MongoDB):
        # Note: db.site_content is Collection[Any] at runtime but Mock in tests
        mock_find_one = cast(Mock, db.site_content.find_one)
        mock_find_one.return_value = {
            "_id": "config",
            "app_description": {"en": "English description", "de": "Deutsche Beschreibung"},
            "logo_url": "/logo.png",
            "favicon_url": "/favicon.ico",
            "font": "Arial",
            "primary_color": "blue",
            "secondary_color": "green",
        }

        settings = db.get_site_settings()

        assert settings.app_description.get("en") == "English description"
        assert settings.app_description.get("de") == "Deutsche Beschreibung"
        assert settings.logo is not None
        assert settings.logo.url == "/logo.png"
        assert settings.favicon_url == "/favicon.ico"
        assert settings.font == "Arial"
        assert settings.primary_color == "blue"
        assert settings.secondary_color == "green"
        # One find_one call for all of the above, not one per field.
        mock_find_one.assert_called_once_with({"_id": "config"})

    def test_get_site_settings_defaults(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = None

        settings = db.get_site_settings()

        assert settings.app_description == {}
        assert settings.logo is None
        assert settings.favicon_url == ""
        assert settings.font == ""
        assert settings.primary_color == "white"
        assert settings.secondary_color == "navy"

    def test_get_blog_meta_forwards_to_site_config(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = {
            "_id": "config",
            "blog_meta": {"en": {"title": "Reading notes", "description": "On Tolkien."}},
        }
        assert db.get_blog_meta("en") == PageMeta(title="Reading notes", description="On Tolkien.")

    def test_get_footer_forwards_to_site_config(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = {
            "_id": "config",
            "footer": {"content": {"en": "Footer"}, "collapsible": True},
        }
        assert db.get_footer("en") == Footer(content="Footer", collapsible=True)

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

    @pytest.fixture
    def db_with_mocked_blog_storage(
        self,
        mock_client: tuple[Mock, Mock],  # noqa: ARG002
    ) -> tuple[MongoDB, Mock]:
        """A MongoDB built with its blog storage mocked out, so delegation can be
        verified through MongoDB's public API."""
        with patch("platzky.db.mongodb_db.MongoBlogStorage") as blog_storage_class:
            db = MongoDB("mongodb://localhost:27017", "test_db")
        return db, blog_storage_class.return_value

    @pytest.mark.usefixtures("mock_client")
    def test_blog_storage_is_built_over_posts_and_pages(self):
        with patch("platzky.db.mongodb_db.MongoBlogStorage") as blog_storage_class:
            db = MongoDB("mongodb://localhost:27017", "test_db")
        blog_storage_class.assert_called_once_with(db.posts, db.pages)

    def test_get_all_posts_delegates(self, db_with_mocked_blog_storage: tuple[MongoDB, Mock]):
        db, blog_storage = db_with_mocked_blog_storage
        blog_storage.posts.get_all.return_value = ["sentinel"]

        assert db.get_all_posts("en") == ["sentinel"]
        blog_storage.posts.get_all.assert_called_once_with("en")

    def test_get_all_pages_delegates(self, db_with_mocked_blog_storage: tuple[MongoDB, Mock]):
        db, blog_storage = db_with_mocked_blog_storage
        blog_storage.pages.get_all.return_value = ["sentinel"]

        assert db.get_all_pages("en") == ["sentinel"]
        blog_storage.pages.get_all.assert_called_once_with("en")

    def test_get_post_delegates(self, db_with_mocked_blog_storage: tuple[MongoDB, Mock]):
        db, blog_storage = db_with_mocked_blog_storage
        blog_storage.posts.get.return_value = "sentinel"

        assert db.get_post("post-1") == "sentinel"
        blog_storage.posts.get.assert_called_once_with("post-1")

    def test_get_page_delegates(self, db_with_mocked_blog_storage: tuple[MongoDB, Mock]):
        db, blog_storage = db_with_mocked_blog_storage
        blog_storage.pages.get.return_value = "sentinel"

        assert db.get_page("page-1") == "sentinel"
        blog_storage.pages.get.assert_called_once_with("page-1")

    def test_get_posts_by_tag_delegates(self, db_with_mocked_blog_storage: tuple[MongoDB, Mock]):
        db, blog_storage = db_with_mocked_blog_storage
        blog_storage.posts.get_by_tag.return_value = ["sentinel"]

        assert db.get_posts_by_tag("tag1", "en") == ["sentinel"]
        blog_storage.posts.get_by_tag.assert_called_once_with("tag1", "en")

    def test_add_comment_delegates(self, db_with_mocked_blog_storage: tuple[MongoDB, Mock]):
        db, blog_storage = db_with_mocked_blog_storage

        db.add_comment("Test User", "Great post!", "post-1")

        blog_storage.posts.add_comment.assert_called_once_with("Test User", "Great post!", "post-1")

    def test_get_plugins_data(self, db: MongoDB):
        cast(Mock, db.plugins.find_one).return_value = {
            "_id": "config",
            "data": {"plugin1": {}},
        }

        plugins = db.get_plugins_data()
        assert len(plugins) == 1
        assert "plugin1" in plugins

    def test_get_plugins_data_no_data(self, db: MongoDB):
        cast(Mock, db.plugins.find_one).return_value = None
        assert db.get_plugins_data() == {}

    def test_get_home_page_path(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = {
            "_id": "config",
            "home_page_path": "/blog/page/about",
        }
        assert db.get_home_page_path("en") == "/blog/page/about"

    def test_get_home_page_path_default(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = None
        assert db.get_home_page_path("en") is None

    def test_get_home_page_path_per_locale(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = {
            "_id": "config",
            "home_page_path": {"default": "/blog/", "pl": "/blog/page/o-nas"},
        }
        assert db.get_home_page_path("pl") == "/blog/page/o-nas"
        assert db.get_home_page_path("en") == "/blog/"

    def test_get_home_page_path_per_locale_no_default(self, db: MongoDB):
        cast(Mock, db.site_content.find_one).return_value = {
            "_id": "config",
            "home_page_path": {"pl": "/blog/page/o-nas"},
        }
        assert db.get_home_page_path("en") is None

    def test_get_home_page_path_present_but_empty_string_is_not_swapped_for_default(
        self, db: MongoDB
    ):
        """Only an absent key falls back to "default" — a present key returns its value as-is."""
        cast(Mock, db.site_content.find_one).return_value = {
            "_id": "config",
            "home_page_path": {"default": "/blog/", "pl": ""},
        }
        assert db.get_home_page_path("pl") == ""

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
