import re
from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest

from platzky import create_app_from_config
from platzky.config import Config
from platzky.engine import Engine
from platzky.platzky import (
    create_app,
    create_engine,
)

_EN = {"name": "English", "flag": "gb", "country": "GB"}
_DE = {"name": "German", "flag": "de", "country": "DE"}
_UK = {"name": "Ukrainian", "flag": "ua", "country": "UA"}


def _engine_with_languages(languages: dict[str, dict[str, str]]) -> Engine:
    config = Config.model_validate(
        {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
            "USE_WWW": False,
            "DEFAULT_LANGUAGE": "en",
            "LANGUAGES": languages,
            "DB": {"TYPE": "json", "DATA": {}},
        }
    )
    return create_engine(config, MagicMock())


class TestPlatzky:
    @pytest.fixture
    def mock_db(self) -> MagicMock:
        return MagicMock()

    def test_change_language_to_domain_language_redirects_to_its_domain(self):
        """Switching to a language with its own domain redirects to that domain's root."""
        app = _engine_with_languages(
            {"en": {**_EN, "domain": "example.com"}, "de": {**_DE, "domain": "example.de"}}
        )
        response = app.test_client().get("/lang/de")
        assert response.status_code == 302
        assert response.headers.get("Location") == "http://example.de/"

    def test_change_language_to_path_language_redirects_to_its_prefix(self):
        """Switching to a language without a domain redirects to its prefix on the main host."""
        app = _engine_with_languages({"en": _EN, "de": _DE})
        response = app.test_client().get("/lang/de")
        assert response.status_code == 302
        assert response.headers.get("Location") == "http://localhost/de/"

    def test_change_language_to_default_language_ignores_the_referrer(self):
        """Switching back to the default language goes to its home, not the referring page."""
        app = _engine_with_languages({"en": _EN, "de": _DE})
        response = app.test_client().get(
            "/lang/en", headers={"Referer": "http://localhost/de/blog/foo"}
        )
        assert response.headers.get("Location") == "http://localhost/"

    def test_change_language_from_a_domain_language_host_goes_to_the_main_domain(self):
        """From another language's domain, a path language is reached via the default's domain."""
        app = _engine_with_languages(
            {
                "en": {**_EN, "domain": "example.com"},
                "de": {**_DE, "domain": "example.de"},
                "uk": _UK,
            }
        )
        response = app.test_client().get("/lang/uk", headers={"Host": "example.de"})
        assert response.headers.get("Location") == "http://example.com/uk/"

    def test_change_language_invalid_locale(self):
        """Test that invalid language codes return 404 and store nothing in the session."""
        app = _engine_with_languages({"en": _EN, "de": _DE})
        with app.test_client() as client:
            response = client.get("/lang/invalid_lang")
            assert response.status_code == 404
            with client.session_transaction() as sess:
                assert "language" not in sess

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
                "TESTING": True,
                "DEBUG": True,
                "DB": {"TYPE": "json", "DATA": {}},
                "FEATURE_FLAGS": {"FAKE_LOGIN": True},
            }
            config = Config.model_validate(config_raw)

            app = create_app_from_config(config)
            app.secret_key = "test_secret_key"  # NOSONAR - hardcoded secret acceptable in tests
            client = app.test_client()

            response = client.get("/login")
            html = response.data.decode("utf-8")

            match = re.search(r'name="csrf_token" value="(.+?)"', html)
            csrf_token = match.group(1) if match else None
            assert csrf_token is not None

            # Invalid role returns 401, no session user set
            response = client.post(
                "/login/verify/fake",
                data={"csrf_token": csrf_token, "role": "invalidrole"},
            )
            assert response.status_code == 401
            with client.session_transaction() as sess:
                assert "user" not in sess

            # GET is not allowed
            response = client.get("/login/verify/fake")
            assert response.status_code == 405
            with client.session_transaction() as sess:
                assert "user" not in sess

            response = client.post(
                "/login/verify/fake",
                follow_redirects=True,
                data={"csrf_token": csrf_token, "role": "admin"},
            )
            assert response.status_code == 200
            with client.session_transaction() as sess:
                assert "user" in sess
                assert sess["user"]["username"] == "admin"
                assert sess["user"]["role"] == "admin"

            response = client.post(
                "/login/verify/fake",
                follow_redirects=True,
                data={"csrf_token": csrf_token, "role": "nonadmin"},
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
        monkeypatch.delenv("FLASK_DEBUG", raising=False)
        config = Config.model_validate(config_raw)

        with pytest.raises(
            RuntimeError,
            match="Cannot register FakeLoginPlugin in production",
        ):
            create_app_from_config(config)
