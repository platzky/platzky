from typing import cast

import pytest
from bs4 import BeautifulSoup, Tag
from werkzeug.test import TestResponse

from platzky.config import Config
from platzky.db.json_db import Json
from platzky.engine import Engine
from platzky.feature_flags import FakeLogin
from platzky.models import CmsModule
from platzky.platzky import create_app_from_config
from tests.unit_tests.fake_app import test_app

test_app = test_app


def test_babel_gets_proper_directories(test_app: Engine):
    with test_app.app_context():
        assert "/some/fake/dir" in list(test_app.babel.domain_instance.translation_directories)


def test_logo_has_set_src(test_app: Engine):
    app = test_app.test_client()
    response = app.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    found_image = soup.find("img")
    assert isinstance(found_image, Tag)
    assert found_image.get("src") is not None
    assert found_image.get("src") == "https://example.com/logo.png"


def test_if_name_is_shown_if_there_is_no_logo(test_app: Engine):
    cast(Json, test_app.db).data["site_content"].pop("logo_url")
    app = test_app.test_client()
    response = app.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.find("img") is None
    branding = soup.find("a", {"class": "navbar-brand"})
    assert branding is not None
    assert branding.get_text() == "testing App Name"


def test_favicon_is_applied(test_app: Engine):
    cast(Json, test_app.db).data["site_content"]["favicon_url"] = "https://example.com/favicon.ico"
    app = test_app.test_client()
    response = app.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    found_ico = soup.find("link", rel="icon")
    assert found_ico is not None
    assert isinstance(found_ico, Tag)
    assert found_ico.get("href") is not None
    assert found_ico.get("href") == "https://example.com/favicon.ico"


def test_notifier(test_app: Engine):
    engine = test_app
    notifier_msg = None

    def notifier(message: str) -> None:
        nonlocal notifier_msg
        notifier_msg = message

    engine.add_notifier(notifier)
    engine.notify("test")
    assert notifier_msg == "test"


@pytest.mark.parametrize("content_type", ["body", "head"])
def test_dynamic_content(test_app: Engine, content_type: str):
    def add_dynamic_element(engine: Engine, content: str) -> None:
        getattr(engine, f"add_dynamic_{content_type}")(content)

    def get_content_text(response: TestResponse, content_type: str) -> str:
        soup = BeautifulSoup(response.data, "html.parser")
        return getattr(soup, content_type).get_text()

    add_dynamic_element(test_app, "test1")
    add_dynamic_element(test_app, "test2")
    app = test_app.test_client()
    response = app.get("/blog/page/test")
    content = get_content_text(response, content_type)
    assert "test1" in content
    assert "test2" in content


@pytest.mark.parametrize("use_www", [True, False])
def test_www_redirects(use_www: bool):
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",
        "USE_WWW": use_www,
        "BLOG_PREFIX": "/blog",
        "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
        "DB": {
            "TYPE": "json",
            "DATA": {
                "site_content": {
                    "pages": [{"title": "test", "slug": "test", "contentInMarkdown": "test"}],
                }
            },
        },
    }
    config = Config.model_validate(config_data)
    app = create_app_from_config(config)
    client = app.test_client()
    client.allow_subdomain_redirects = True

    if use_www:
        url = "http://localhost/blog/page/test"
        expected_redirect = "http://www.localhost/blog/page/test"
    else:
        url = "http://www.localhost/blog/page/test"
        expected_redirect = "http://localhost/blog/page/test"

    response = client.get(url, follow_redirects=False)

    assert response.request.url == url
    assert response.location == expected_redirect


def test_that_default_page_title_is_app_name(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.title is not None
    assert soup.title.string == "testing App Name"


@pytest.mark.parametrize(
    ("tag", "subtag", "value"), [("link", "hreflang", "en"), ("html", "lang", "en-GB")]
)
def test_that_tag_has_proper_value(test_app: Engine, tag: str, subtag: str, value: str):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert getattr(soup, tag) is not None
    assert getattr(soup, tag).get(subtag) == value


def test_that_logo_has_proper_alt_text(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    logo_img = soup.find("img", class_="logo")
    assert isinstance(logo_img, Tag)
    assert logo_img.get("alt") == "testing App Name logo"


def test_that_logo_link_has_proper_aria_label_text(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    logo_link = soup.find("a", class_="navbar-brand")
    assert isinstance(logo_link, Tag)
    assert logo_link.get("aria-label") == "Link to home page"


def test_that_language_menu_has_proper_code(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    language_menu = soup.find("span", class_="language-indicator-text")
    assert isinstance(language_menu, Tag)
    assert language_menu.get_text() == "en"


def test_that_language_switch_has_proper_aria_label_text(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    logo_link = soup.find("button", id="languages-menu")
    assert isinstance(logo_link, Tag)
    assert (
        logo_link.get("aria-label")
        == "Language switch icon, used to change the language of the website"
    )


def test_that_page_has_proper_html_lang_attribute(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.html is not None
    assert soup.html.get("lang") == "en-GB"


def test_add_login_method(test_app: Engine):
    def sample_login_method():
        return "Login Method"

    test_app.add_login_method(sample_login_method)
    assert sample_login_method in test_app.login_methods

    app = test_app.test_client()
    response = app.get("/admin/", follow_redirects=True)

    assert response.status_code == 200
    assert b"Login Method" in response.data


def test_add_cms_module(test_app: Engine):
    module = CmsModule(
        slug="test-module", template="test.html", name="Test Module", description="Test Description"
    )
    test_app.add_cms_module(module)
    assert module in test_app.cms_modules


def test_health_liveness_endpoint(test_app: Engine):
    """Test that /health/liveness returns alive status"""
    client = test_app.test_client()
    response = client.get("/health/liveness")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "alive"


def test_health_alias_endpoint(test_app: Engine):
    """Test that /health is an alias for /health/liveness"""
    client = test_app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "alive"


def test_health_readiness_endpoint_healthy(test_app: Engine):
    """Test that /health/readiness returns ready when database is ok"""
    client = test_app.test_client()
    response = client.get("/health/readiness")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "ready"
    assert json_data["checks"]["database"] == "ok"


def test_health_readiness_endpoint_db_failure(test_app: Engine):
    """Test that /health/readiness returns not_ready when database fails"""
    # Make the database raise an error
    original_method = test_app.db.health_check

    def mock_db_failure():
        raise Exception("DB connection failed")

    test_app.db.health_check = mock_db_failure

    client = test_app.test_client()
    response = client.get("/health/readiness")
    assert response.status_code == 503
    json_data = response.get_json()
    assert json_data["status"] == "not_ready"
    assert json_data["checks"]["database"] == "failed: DB connection failed"

    # Restore original method
    test_app.db.health_check = original_method


def test_add_health_check_success(test_app: Engine):
    """Test adding a custom health check that succeeds"""
    check_called = []

    def custom_check():
        check_called.append(True)

    test_app.add_health_check("custom_service", custom_check)

    client = test_app.test_client()
    response = client.get("/health/readiness")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "ready"
    assert json_data["checks"]["custom_service"] == "ok"
    assert len(check_called) == 1


def test_add_health_check_failure(test_app: Engine):
    """Test adding a custom health check that fails"""

    def failing_check():
        raise Exception("Custom service unavailable")

    test_app.add_health_check("failing_service", failing_check)

    client = test_app.test_client()
    response = client.get("/health/readiness")
    assert response.status_code == 503
    json_data = response.get_json()
    assert json_data["status"] == "not_ready"
    assert json_data["checks"]["failing_service"] == "failed: Custom service unavailable"


def test_multiple_health_checks(test_app: Engine):
    """Test multiple custom health checks with mixed results"""

    def check_ok():
        pass

    def check_fail():
        raise Exception("Service down")

    test_app.add_health_check("service1", check_ok)
    test_app.add_health_check("service2", check_fail)

    client = test_app.test_client()
    response = client.get("/health/readiness")
    assert response.status_code == 503
    json_data = response.get_json()
    assert json_data["status"] == "not_ready"
    assert json_data["checks"]["service1"] == "ok"
    assert json_data["checks"]["service2"] == "failed: Service down"
    assert json_data["checks"]["database"] == "ok"


def test_health_check_db_timeout(test_app: Engine):
    """Test that database health check times out and doesn't block"""
    import time

    original_method = test_app.db.health_check

    def slow_health_check():
        time.sleep(15)  # Longer than timeout

    test_app.db.health_check = slow_health_check

    # Temporarily reduce timeout for faster test
    # We can't easily mock the timeout, so we test the actual timeout behavior
    # by using a blocking call that exceeds the timeout
    client = test_app.test_client()

    # This should timeout (default is 10s, our check sleeps 15s)
    # For test speed, we'll mock the Future.result instead
    from concurrent.futures import TimeoutError
    from unittest.mock import patch

    with patch("concurrent.futures.Future.result") as mock_result:
        mock_result.side_effect = TimeoutError()

        response = client.get("/health/readiness")

        assert response.status_code == 503
        json_data = response.get_json()
        assert json_data["status"] == "not_ready"
        assert json_data["checks"]["database"] == "failed: timeout"

    test_app.db.health_check = original_method


def test_health_check_custom_timeout(test_app: Engine):
    """Test that custom health check times out and doesn't block"""
    from concurrent.futures import TimeoutError
    from unittest.mock import patch

    def slow_check():
        import time

        time.sleep(15)

    test_app.add_health_check("slow_service", slow_check)

    # Mock Future.result to simulate timeout on the second call (custom check)
    call_count = [0]

    def mock_result(timeout: float | None = None) -> None:  # noqa: ARG001
        call_count[0] += 1
        if call_count[0] == 1:
            # First call (db check) succeeds
            return None
        # Second call (custom check) times out
        raise TimeoutError()

    with patch("concurrent.futures.Future.result", side_effect=mock_result):
        client = test_app.test_client()
        response = client.get("/health/readiness")

        assert response.status_code == 503
        json_data = response.get_json()
        assert json_data["status"] == "not_ready"
        assert json_data["checks"]["slow_service"] == "failed: timeout"


def test_add_health_check_not_callable(test_app: Engine):
    """Test that adding a non-callable health check raises TypeError"""
    with pytest.raises(TypeError, match="check_function must be callable"):
        test_app.add_health_check("invalid", "not a function")  # type: ignore[arg-type] - Intentionally passing invalid type to test error handling


def test_is_enabled(test_app: Engine):
    """Test that engine.is_enabled works with Flag classes"""
    assert test_app.is_enabled(FakeLogin) is False


def test_get_all_feature_flags(test_app: Engine):
    """Test that get_all_feature_flags returns flag metadata"""
    flags = test_app.get_all_feature_flags()

    assert "FAKE_LOGIN" in flags
    assert flags["FAKE_LOGIN"]["alias"] == "FAKE_LOGIN"
    assert flags["FAKE_LOGIN"]["default"] is False
    assert isinstance(flags["FAKE_LOGIN"]["description"], str)
    assert "value" in flags["FAKE_LOGIN"]
    assert flags["FAKE_LOGIN"]["typed"] is True


def test_get_all_feature_flags_with_enabled_flag():
    """Test get_all_feature_flags with fake_login enabled"""
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",
        "BLOG_PREFIX": "/blog",
        "TESTING": True,  # Required for FAKE_LOGIN
        "FEATURE_FLAGS": {"FAKE_LOGIN": True},
        "DB": {
            "TYPE": "json",
            "DATA": {
                "site_content": {
                    "pages": [{"title": "test", "slug": "test", "contentInMarkdown": "test"}],
                }
            },
        },
    }
    config = Config.model_validate(config_data)
    app = create_app_from_config(config)

    assert app.is_enabled(FakeLogin) is True

    flags = app.get_all_feature_flags()
    assert flags["FAKE_LOGIN"]["value"] is True
    assert flags["FAKE_LOGIN"]["typed"] is True


def test_get_all_feature_flags_includes_unregistered():
    """Test that get_all_feature_flags includes unregistered flags."""
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",
        "BLOG_PREFIX": "/blog",
        "FEATURE_FLAGS": {"CUSTOM_FLAG": True},
        "DB": {
            "TYPE": "json",
            "DATA": {
                "site_content": {
                    "pages": [{"title": "test", "slug": "test", "contentInMarkdown": "test"}],
                }
            },
        },
    }
    config = Config.model_validate(config_data)
    app = create_app_from_config(config)

    flags = app.get_all_feature_flags()

    # Registered flag should be present
    assert "FAKE_LOGIN" in flags
    assert flags["FAKE_LOGIN"]["typed"] is True

    # Unregistered flag should also be present
    assert "CUSTOM_FLAG" in flags
    assert flags["CUSTOM_FLAG"]["value"] is True
    assert flags["CUSTOM_FLAG"]["typed"] is False
    assert "deprecated" in flags["CUSTOM_FLAG"]["description"].lower()
