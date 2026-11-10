import gc
from unittest.mock import Mock, patch

import pytest

from platzky.db.exceptions import InvalidSiteContentError, NotFoundError
from platzky.db.mongodb_db import MongoDB, MongoDbConfig, db_from_config


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
            mock_db.localized_content = Mock()
            mock_db.plugins = Mock()
            mock_db.site_content.find_one.return_value = None
            mock_db.localized_content.find.return_value = []

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

    def test_exposes_the_three_repositories(self, db: MongoDB, mock_db: Mock):
        mock_db.posts.find_one.return_value = None
        mock_db.plugins.find_one.return_value = {"_id": "config", "data": {"plugin1": {}}}
        mock_db.localized_content.find_one.return_value = {
            "_id": "en",
            "home_page_path": "/blog/page/about",
        }

        assert list(db.plugin_config.get_all()) == ["plugin1"]
        assert db.site_config.get_localized_content("en").home_page_path == "/blog/page/about"
        with pytest.raises(NotFoundError):
            db.blog.posts.get("missing")

    def test_init(self, mock_client: tuple[Mock, Mock]):
        mock_client_instance, _ = mock_client
        db = MongoDB("mongodb://localhost:27017", "test_db")

        assert db.connection_string == "mongodb://localhost:27017"
        assert db.database_name == "test_db"
        mock_client_instance.assert_called_once_with("mongodb://localhost:27017")

    def test_database_is_the_database_the_facade_uses(self, db: MongoDB, mock_db: Mock):
        mock_db.site_content.find_one.return_value = None
        mock_db.localized_content.find_one.return_value = None

        db.site_config.get_site_content()

        assert db.database is mock_db
        mock_db.site_content.find_one.assert_called()

    def test_invalid_site_content_stops_the_facade_from_being_created(self, mock_db: Mock):
        mock_db.site_content.find_one.return_value = {"_id": "config", "menu_items": {}}
        mock_db.localized_content.find.return_value = [{"_id": "pl", "footer": None}]

        with pytest.raises(InvalidSiteContentError):
            MongoDB("mongodb://localhost:27017", "test_db")

    def test_database_is_not_closed_when_the_facade_is_collected(
        self, mock_client: tuple[Mock, Mock]
    ):
        mongo_client, _ = mock_client
        facade = MongoDB("mongodb://localhost:27017", "test_db")
        database = facade.database

        del facade
        gc.collect()

        assert database is mongo_client.return_value["test_db"]
        mongo_client.return_value.close.assert_not_called()

    def test_health_check_success(self, db: MongoDB, mongo_client: Mock):
        """Test health check when database is accessible"""
        mock_command = mongo_client.return_value.admin.command
        mock_command.return_value = {"ok": 1}

        # Should not raise any exception
        db.health_check()

        mock_command.assert_called_once_with("ping")

    def test_health_check_fails_on_site_content_made_invalid_after_start(
        self, db: MongoDB, mock_db: Mock
    ):
        mock_db.localized_content.find.return_value = [{"_id": "pl", "unknown": "x"}]

        with pytest.raises(InvalidSiteContentError):
            db.health_check()

    def test_health_check_failure(self, db: MongoDB, mongo_client: Mock):
        """Test health check when database is not accessible"""
        mongo_client.return_value.admin.command.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            db.health_check()
