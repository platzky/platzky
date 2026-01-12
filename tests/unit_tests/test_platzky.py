import re
from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest

from platzky import create_app_from_config
from platzky.config import Config, LanguageConfig
from platzky.platzky import (
    create_app,
    create_engine,
)


class TestPlatzky:
    @pytest.fixture
    def mock_db(self) -> MagicMock:
        return MagicMock()

    def test_change_language_with_domain(self, mock_db: MagicMock):
        """Test the change_language function when a domain is specified."""
        mock_config = MagicMock()
        mock_config.languages = {
            "en": LanguageConfig(name="English", flag="gb", country="GB", domain="example.com"),
            "de": LanguageConfig(name="German", flag="de", country="DE", domain="example.de"),
        }

        app = create_engine(mock_config, mock_db)

        with app.test_request_context():
            mock_config.use_www = False
            app.secret_key = "test_secret_key"
            response = app.test_client().get("/lang/de", follow_redirects=False)
            assert response.status_code == 302
            assert response.headers["Location"] == "http://example.de"

    def test_change_language_without_domain(self, mock_db: MagicMock):
        """Test the change_language function when no domain is specified."""
        mock_config = MagicMock()
        mock_config.languages = {
            "en": LanguageConfig(name="English", flag="gb", country="GB", domain=None),
            "de": LanguageConfig(name="German", flag="de", country="DE", domain=None),
        }

        app = create_engine(mock_config, mock_db)

        with app.test_request_context():
            mock_config.use_www = False
            app.secret_key = "test_secret_key"
            response = app.test_client().get("/lang/de", follow_redirects=False)
            assert response.status_code == 302
            # When request.referrer is None, it should redirect to "/" instead
            assert response.headers["Location"] == "/"

    def test_change_language_invalid_locale(self, mock_db: MagicMock):
        """Test that invalid language codes return 404."""
        mock_config = MagicMock()
        mock_config.languages = {
            "en": LanguageConfig(name="English", flag="gb", country="GB", domain=None),
            "de": LanguageConfig(name="German", flag="de", country="DE", domain=None),
        }

        app = create_engine(mock_config, mock_db)

        with app.test_request_context():
            mock_config.use_www = False
            app.secret_key = "test_secret_key"

            # Verify that session language does not get set to invalid language
            with app.test_client() as client:
                response = client.get("/lang/invalid_lang", follow_redirects=False)
                assert response.status_code == 404

                # Check that the invalid language was NOT set in session
                with client.session_transaction() as sess:
                    # Session might have a default language, but shouldn't be 'invalid_lang'
                    assert sess.get("language") != "invalid_lang"

    def test_url_link(self, mock_db: MagicMock):
        """Test the url_link function."""

        def url_link_func(x: object) -> str:
            return str(x)

        def context_proc() -> dict[str, Callable[[object], str]]:
            return {"url_link": url_link_func}

        mock_config = MagicMock()
        mock_config.context_processor_functions = [context_proc]

        app = create_engine(mock_config, mock_db)
        mock_processor = MagicMock()

        def url_link_func2(x: object) -> str:
            return str(x)

        mock_processor.return_value = {"url_link": url_link_func2}

        with app.test_request_context():
            url_link = mock_processor.return_value["url_link"]
            assert url_link("test") == "test"

    def test_create_app(self):
        """Test the create_app function."""
        with patch("platzky.platzky.Config.parse_yaml") as mock_parse_yaml:
            with patch("platzky.platzky.create_app_from_config") as mock_create_app_from_config:
                mock_config = MagicMock()
                mock_parse_yaml.return_value = mock_config
                mock_engine = MagicMock()
                mock_create_app_from_config.return_value = mock_engine

                result = create_app("test_config.yml")

                mock_parse_yaml.assert_called_once_with("test_config.yml")
                mock_create_app_from_config.assert_called_once_with(mock_config)
                assert result == mock_engine

    def test_fake_login_routes(self, mock_db: MagicMock):
        """Test the fake login routes."""
        with patch("platzky.platzky.get_db") as mock_get_db:
            mock_get_db.return_value = mock_db

            config_raw = {
                "USE_WWW": False,
                "APP_NAME": "testing App Name",
                "SECRET_KEY": "secret",
                "SEO_PREFIX": "/seo",
                "DB": {"TYPE": "json", "DATA": {}},
                "FEATURE_FLAGS": {"FAKE_LOGIN": True},
            }
            config = Config.model_validate(config_raw)

            app = create_app_from_config(config)
            app.secret_key = "test_secret_key"
            client = app.test_client()

            response = client.get("/admin/")
            html = response.data.decode("utf-8")

            match = re.search(r'name="csrf_token" type="hidden" value="(.+?)"', html)
            csrf_token = match.group(1) if match else None
            assert csrf_token is not None

            response = client.post(
                "/admin/fake-login/invalidrole",
                follow_redirects=True,
                data={"csrf_token": csrf_token},
            )
            assert response.status_code == 200
            with client.session_transaction() as sess:
                assert "user" not in sess

            response = client.get("/admin/fake-login/admin")
            assert response.status_code == 405  # Method Not Allowed

            # Ensure no user is set in the session after attempting GET request
            with client.session_transaction() as sess:
                assert "user" not in sess

            response = client.post(
                "/admin/fake-login/admin", follow_redirects=True, data={"csrf_token": csrf_token}
            )
            assert response.status_code == 200
            with client.session_transaction() as sess:
                assert "user" in sess
                assert sess["user"]["username"] == "admin"
                assert sess["user"]["role"] == "admin"

            response = client.post(
                "/admin/fake-login/nonadmin", follow_redirects=True, data={"csrf_token": csrf_token}
            )
            assert response.status_code == 200
            with client.session_transaction() as sess:
                assert "user" in sess
                assert sess["user"]["username"] == "user"
                assert sess["user"]["role"] == "nonadmin"

    def test_fake_login_is_blocked_on_nondev_env(self, monkeypatch: pytest.MonkeyPatch):
        """Test that fake login is blocked on non-development environments."""
        config_raw = {
            "USE_WWW": False,
            "APP_NAME": "testing App Name",
            "SECRET_KEY": "secret",
            "SEO_PREFIX": "/seo",
            "DB": {"TYPE": "json", "DATA": {}},
            "FEATURE_FLAGS": {"FAKE_LOGIN": True},
        }

        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        config = Config.model_validate(config_raw)

        with pytest.raises(
            RuntimeError,
            match="SECURITY ERROR: Fake login routes are enabled outside of a testing environment! "
            "This functionality must only be used during development or testing.",
        ):
            create_app_from_config(config)
