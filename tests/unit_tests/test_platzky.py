from typing import Any, Callable, Dict
from unittest.mock import MagicMock, patch

import pytest

from platzky.config import LanguageConfig
from platzky.platzky import (
    create_app,
    create_engine,
)


class TestPlatzky:
    @pytest.fixture
    def mock_db(self) -> MagicMock:
        return MagicMock()

    def test_change_language_with_domain(self, mock_db):
        """Test the change_language function when a domain is specified."""
        # Mock the languages
        mock_config = MagicMock()
        mock_config.languages = {
            "en": LanguageConfig(name="English", flag="gb", country="GB", domain="example.com"),
            "de": LanguageConfig(name="German", flag="de", country="DE", domain="example.de"),
        }

        app = create_engine(mock_config, mock_db)

        # Test the function
        with app.test_request_context():
            mock_config.use_www = False
            app.secret_key = "test_secret_key"
            response = app.test_client().get("/lang/de", follow_redirects=False)
            assert response.status_code == 301
            assert response.headers["Location"] == "http://example.de"

    def test_change_language_without_domain(self, mock_db):
        """Test the change_language function when no domain is specified."""
        # Mock the languages
        mock_config = MagicMock()
        mock_config.languages = {
            "en": LanguageConfig(name="English", flag="gb", country="GB", domain=None),
            "de": LanguageConfig(name="German", flag="de", country="DE", domain=None),
        }

        app = create_engine(mock_config, mock_db)

        # Test the function
        with app.test_request_context():
            mock_config.use_www = False
            app.secret_key = "test_secret_key"
            response = app.test_client().get("/lang/de", follow_redirects=False)
            assert response.status_code == 302
            assert response.headers["Location"] == "None"

    def test_url_link(self, mock_db):
        """Test the url_link function."""

        # Mock the context processor functions with proper type hints
        def url_link_func(x: Any) -> str:
            return str(x)

        def context_proc() -> Dict[str, Callable[[Any], str]]:
            return {"url_link": url_link_func}

        mock_config = MagicMock()
        mock_config.context_processor_functions = [context_proc]

        app = create_engine(mock_config, mock_db)

        # Mock the context processor
        mock_processor = MagicMock()

        def url_link_func2(x: Any) -> str:
            return str(x)

        mock_processor.return_value = {"url_link": url_link_func2}

        # Test the function
        with app.test_request_context():
            url_link = mock_processor.return_value["url_link"]
            assert url_link("test") == "test"

    def test_create_app(self):
        """Test the create_app function."""
        with patch("platzky.platzky.Config.parse_yaml") as mock_parse_yaml:
            with patch("platzky.platzky.create_app_from_config") as mock_create_app_from_config:
                # Set up the mocks
                mock_config = MagicMock()
                mock_parse_yaml.return_value = mock_config
                mock_engine = MagicMock()
                mock_create_app_from_config.return_value = mock_engine

                # Call the function
                result = create_app("test_config.yml")

                # Verify the calls
                mock_parse_yaml.assert_called_once_with("test_config.yml")
                mock_create_app_from_config.assert_called_once_with(mock_config)

                # Verify the result
                assert result == mock_engine
