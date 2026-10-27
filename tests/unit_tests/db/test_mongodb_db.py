from unittest.mock import Mock, patch

import pytest

from platzky.db.exceptions import NotFoundError
from platzky.db.mongodb_db import MongoDB, MongoDbConfig, db_from_config
from platzky.models import Footer, MenuItem, PageMeta, Post


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
    def mock_db(self, mock_client: tuple[Mock, Mock]) -> Mock:
        return mock_client[1]

    @pytest.fixture
    def mongo_client(self, mock_client: tuple[Mock, Mock]) -> Mock:
        return mock_client[0]

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

    def test_get_site_settings(self, db: MongoDB, mock_db: Mock):
        mock_find_one = mock_db.site_content.find_one
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

    def test_get_blog_meta_forwards_to_site_config(self, db: MongoDB, mock_db: Mock):
        mock_db.site_content.find_one.return_value = {
            "_id": "config",
            "blog_meta": {"en": {"title": "Reading notes", "description": "On Tolkien."}},
        }
        assert db.get_blog_meta("en") == PageMeta(title="Reading notes", description="On Tolkien.")

    def test_get_footer_forwards_to_site_config(self, db: MongoDB, mock_db: Mock):
        mock_db.site_content.find_one.return_value = {
            "_id": "config",
            "footer": {"content": {"en": "Footer"}, "collapsible": True},
        }
        assert db.get_footer("en") == Footer(content="Footer", collapsible=True)

    def test_get_menu_items_in_lang(self, db: MongoDB, mock_db: Mock):
        # Mock menu items data
        mock_find_one = mock_db.menu_items.find_one
        mock_find_one.return_value = {
            "_id": "en",
            "items": [{"name": "Home", "url": "/", "weight": 1}],
        }

        menu_items = db.get_menu_items_in_lang("en")

        assert len(menu_items) == 1
        assert isinstance(menu_items[0], MenuItem)
        assert menu_items[0].name == "Home"
        mock_find_one.assert_called_once_with({"_id": "en"})

    def test_get_menu_items_in_lang_no_data(self, db: MongoDB, mock_db: Mock):
        mock_db.menu_items.find_one.return_value = None
        menu_items = db.get_menu_items_in_lang("fr")
        assert len(menu_items) == 0

    def test_get_plugins_data(self, db: MongoDB, mock_db: Mock):
        mock_db.plugins.find_one.return_value = {
            "_id": "config",
            "data": {"plugin1": {}},
        }

        plugins = db.get_plugins_data()
        assert len(plugins) == 1
        assert "plugin1" in plugins

    def test_get_plugins_data_no_data(self, db: MongoDB, mock_db: Mock):
        mock_db.plugins.find_one.return_value = None
        assert db.get_plugins_data() == {}

    def test_get_home_page_path(self, db: MongoDB, mock_db: Mock):
        mock_db.site_content.find_one.return_value = {
            "_id": "config",
            "home_page_path": "/blog/page/about",
        }
        assert db.get_home_page_path("en") == "/blog/page/about"

    def test_connection_closed_on_deletion(self, mock_client: tuple[Mock, Mock]):
        mongo_client, _ = mock_client
        db = MongoDB("mongodb://localhost:27017", "test_db")

        del db

        mongo_client.return_value.close.assert_called_once()

    def test_health_check_success(self, db: MongoDB, mongo_client: Mock):
        """Test health check when database is accessible"""
        mock_command = mongo_client.return_value.admin.command
        mock_command.return_value = {"ok": 1}

        # Should not raise any exception
        db.health_check()

        mock_command.assert_called_once_with("ping")

    def test_health_check_failure(self, db: MongoDB, mongo_client: Mock):
        """Test health check when database is not accessible"""
        mongo_client.return_value.admin.command.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            db.health_check()

    def test_get_all_posts(self, db: MongoDB, mock_db: Mock):
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

        mock_find = mock_db.posts.find
        mock_find.return_value = mock_posts

        posts = db.get_all_posts("en")

        assert len(posts) == 1
        assert isinstance(posts[0], Post)
        assert posts[0].title == "Post 1"
        mock_find.assert_called_once_with({"language": "en"})

    def test_get_post(self, db: MongoDB, mock_db: Mock):
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

        mock_find_one = mock_db.posts.find_one
        mock_find_one.return_value = mock_post

        post = db.get_post("post-1")

        assert isinstance(post, Post)
        assert post.title == "Post 1"
        mock_find_one.assert_called_once_with({"slug": "post-1"})

    def test_get_post_not_found(self, db: MongoDB, mock_db: Mock):
        mock_db.posts.find_one.return_value = None

        with pytest.raises(NotFoundError, match="Post with slug non-existent not found"):
            db.get_post("non-existent")

    def test_get_all_pages(self, db: MongoDB, mock_db: Mock):
        mock_find = mock_db.pages.find
        mock_find.return_value = [
            {
                "title": "About Tolkien",
                "slug": "about-tolkien",
                "author": "Test Author",
                "contentInMarkdown": "# About",
                "excerpt": "excerpt",
                "language": "en",
                "coverImage": {"url": "/images/tolkien.jpg"},
            }
        ]

        pages = db.get_all_pages("en")

        assert [page.slug for page in pages] == ["about-tolkien"]
        mock_find.assert_called_once_with({"language": "en"})

    def test_get_page(self, db: MongoDB, mock_db: Mock):
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

        mock_find_one = mock_db.pages.find_one
        mock_find_one.return_value = mock_page

        page = db.get_page("page-1")

        assert isinstance(page, Post)  # Page is actually Post type in platzky
        assert page.title == "Page 1"
        mock_find_one.assert_called_once_with({"slug": "page-1"})

    def test_get_page_not_found(self, db: MongoDB, mock_db: Mock):
        mock_db.pages.find_one.return_value = None

        with pytest.raises(NotFoundError, match="Page with slug non-existent not found"):
            db.get_page("non-existent")

    def test_get_posts_by_tag(self, db: MongoDB, mock_db: Mock):
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
        mock_find = mock_db.posts.find
        mock_find.return_value = mock_posts

        result = db.get_posts_by_tag("tag1", "en")

        assert len(result) == 1
        assert isinstance(result[0], Post)
        assert result[0].title == "Tagged Post"
        mock_find.assert_called_once_with({"tags": "tag1", "language": "en"})

    def test_add_comment(self, db: MongoDB, mock_db: Mock):
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

            mock_db.posts.update_one.assert_called_once_with(
                {"slug": "post-1"}, {"$push": {"comments": expected_comment}}
            )
