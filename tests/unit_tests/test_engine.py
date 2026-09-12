from typing import Any, cast

import pytest
from bs4 import BeautifulSoup, Tag
from flask import url_for
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
        "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
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


def _build_home_page_test_app(
    site_content: dict[str, Any],
    languages: dict[str, Any] | None = None,
    default_language: str | None = None,
):
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
        "USE_WWW": False,
        "BLOG_PREFIX": "/blog",
        "DEFAULT_LANGUAGE": default_language,
        "LANGUAGES": languages or {},
        "DB": {"TYPE": "json", "DATA": {"site_content": site_content}},
    }
    config = Config.model_validate(config_data)
    return create_app_from_config(config)


def test_home_page_renders_configured_page():
    app = _build_home_page_test_app(
        {
            "home_page_path": "/blog/page/about",
            "pages": [
                {
                    "title": "About us",
                    "slug": "about",
                    "contentInMarkdown": "Hello there",
                    "author": "author",
                    "excerpt": "excerpt",
                }
            ],
        }
    )
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert b"Hello there" in response.data


def test_home_page_renders_configured_post():
    app = _build_home_page_test_app(
        {
            "home_page_path": "/blog/welcome-post",
            "posts": [
                {
                    "title": "Welcome",
                    "slug": "welcome-post",
                    "language": "en",
                    "excerpt": "excerpt",
                    "author": "author",
                    "tags": [],
                    "contentInMarkdown": "Welcome to the site",
                    "date": "2021-02-19",
                    "comments": [],
                }
            ],
        }
    )
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert b"Welcome to the site" in response.data


def test_home_page_falls_back_to_blog_index_when_not_configured():
    app = _build_home_page_test_app(
        {
            "posts": [
                {
                    "title": "Latest post",
                    "slug": "latest-post",
                    "language": "en",
                    "excerpt": "excerpt",
                    "author": "author",
                    "tags": [],
                    "contentInMarkdown": "content",
                    "date": "2021-02-19",
                    "comments": [],
                }
            ],
        }
    )
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert b"Latest post" in response.data


_BILINGUAL_LANGUAGES = {
    "en": {"name": "English", "flag": "us", "country": "US"},
    "pl": {"name": "Polski", "flag": "pl", "country": "PL"},
}
_ABOUT_PAGES = [
    {
        "title": "About us",
        "slug": "about",
        "contentInMarkdown": "Hello there",
        "author": "author",
        "excerpt": "excerpt",
    },
    {
        "title": "O nas",
        "slug": "o-nas",
        "contentInMarkdown": "Witaj",
        "author": "author",
        "excerpt": "excerpt",
    },
]


def _build_bilingual_home_page_test_app(pl_home_path: str = "/blog/page/o-nas") -> Engine:
    return _build_home_page_test_app(
        {
            "home_page_path": {"default": "/blog/page/about", "pl": pl_home_path},
            "pages": _ABOUT_PAGES,
        },
        languages=_BILINGUAL_LANGUAGES,
        default_language="en",
    )


def test_home_page_ignores_accept_language():
    app = _build_bilingual_home_page_test_app()
    response = app.test_client().get("/", headers={"Accept-Language": "pl"})
    assert response.status_code == 200
    assert b"Hello there" in response.data


@pytest.mark.parametrize("pl_home_path", ["/blog/page/o-nas", "/pl/blog/page/o-nas"])
def test_home_page_resolves_path_language_home(pl_home_path: str):
    app = _build_bilingual_home_page_test_app(pl_home_path)
    response = app.test_client().get("/pl/")
    assert response.status_code == 200
    assert b"Witaj" in response.data


def test_home_page_404s_when_configured_path_does_not_resolve():
    app = _build_home_page_test_app({"home_page_path": "/blog/page/does-not-exist"})
    response = app.test_client().get("/")
    assert response.status_code == 404


def test_home_page_falls_back_when_configured_path_is_root():
    app = _build_home_page_test_app(
        {
            "home_page_path": "/",
            "posts": [
                {
                    "title": "Latest post",
                    "slug": "latest-post",
                    "language": "en",
                    "excerpt": "excerpt",
                    "author": "author",
                    "tags": [],
                    "contentInMarkdown": "content",
                    "date": "2021-02-19",
                    "comments": [],
                }
            ],
        }
    )
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert b"Latest post" in response.data


def test_that_404_page_title_includes_app_name(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.title is not None
    # En dash matches 404.html's actual rendered title, not a typo for a hyphen.
    assert soup.title.string == "Page not found – testing App Name"  # noqa: RUF001


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


def test_that_logo_link_has_no_redundant_aria_label(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    logo_link = soup.find("a", class_="navbar-brand")
    assert isinstance(logo_link, Tag)
    # aria-label removed: link content (logo alt text or app name) provides the accessible name
    assert logo_link.get("aria-label") is None


def test_that_language_menu_has_proper_code(test_app: Engine):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    language_menu = soup.find("span", class_="language-indicator-text")
    assert isinstance(language_menu, Tag)
    assert language_menu.get_text() == "en"


def _build_dedicated_domain_test_app() -> Engine:
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
        "USE_WWW": False,
        "BLOG_PREFIX": "/blog",
        "DEFAULT_LANGUAGE": "en",
        "LANGUAGES": {
            "en": {"name": "English", "flag": "gb", "country": "GB", "domain": "en.example.com"},
            "pl": {"name": "polski", "flag": "pl", "country": "PL", "domain": "pl.example.com"},
        },
        "DB": {"TYPE": "json", "DATA": {"site_content": {}}},
    }
    config = Config.model_validate(config_data)
    return create_app_from_config(config)


def test_locale_defaults_to_the_language_whose_domain_is_being_visited():
    # Regression test: a visitor landing directly on a language's dedicated domain
    # should see that language, not the default one.
    app = _build_dedicated_domain_test_app()
    response = app.test_client().get("/", headers={"Host": "pl.example.com"})
    soup = BeautifulSoup(response.data, "html.parser")
    language_menu = soup.find("span", class_="language-indicator-text")
    assert isinstance(language_menu, Tag)
    assert language_menu.get_text() == "pl"


def test_locale_defaults_to_the_language_whose_domain_includes_a_port():
    # Regression test: domain configs that include an explicit port (e.g. local/staging
    # setups like "pl.example.com:5000") must still match the request host's port.
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
        "USE_WWW": False,
        "BLOG_PREFIX": "/blog",
        "DEFAULT_LANGUAGE": "en",
        "LANGUAGES": {
            "en": {
                "name": "English",
                "flag": "gb",
                "country": "GB",
                "domain": "en.example.com:5000",
            },
            "pl": {
                "name": "polski",
                "flag": "pl",
                "country": "PL",
                "domain": "pl.example.com:5000",
            },
        },
        "DB": {"TYPE": "json", "DATA": {"site_content": {}}},
    }
    config = Config.model_validate(config_data)
    app = create_app_from_config(config)
    response = app.test_client().get("/", headers={"Host": "pl.example.com:5000"})
    soup = BeautifulSoup(response.data, "html.parser")
    language_menu = soup.find("span", class_="language-indicator-text")
    assert isinstance(language_menu, Tag)
    assert language_menu.get_text() == "pl"


def test_locale_does_not_match_domain_on_a_different_port():
    # Regression test: a domain with an explicit port must not match a request on a
    # different port, even though the hostname is identical.
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
        "USE_WWW": False,
        "BLOG_PREFIX": "/blog",
        "DEFAULT_LANGUAGE": "en",
        "LANGUAGES": {
            "en": {"name": "English", "flag": "gb", "country": "GB", "domain": "example.com"},
            "pl": {
                "name": "polski",
                "flag": "pl",
                "country": "PL",
                "domain": "pl.example.com:5000",
            },
        },
        "DB": {"TYPE": "json", "DATA": {"site_content": {}}},
    }
    config = Config.model_validate(config_data)
    app = create_app_from_config(config)
    response = app.test_client().get("/", headers={"Host": "pl.example.com:6000"})
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
        # Intentionally empty: a health check that doesn't raise is considered successful
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
    """Test that engine.is_enabled works with FeatureFlag instances"""
    assert test_app.is_enabled(FakeLogin) is False


def test_is_enabled_with_flag_on():
    """Test engine.is_enabled with fake_login enabled"""
    config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
        "BLOG_PREFIX": "/blog",
        "TESTING": True,
        "DEBUG": True,
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


def _language_indicator(response: TestResponse) -> str:
    soup = BeautifulSoup(response.data, "html.parser")
    indicator = soup.find("span", class_="language-indicator-text")
    assert isinstance(indicator, Tag)
    return indicator.get_text()


def _hreflang_urls(response: TestResponse) -> dict[str, str]:
    soup = BeautifulSoup(response.data, "html.parser")
    return {
        str(link.get("hreflang")): str(link.get("href"))
        for link in soup.find_all("link")
        if link.get("hreflang")
    }


def _link_hrefs(response: TestResponse) -> list[str]:
    soup = BeautifulSoup(response.data, "html.parser")
    return [str(a.get("href")) for a in soup.find_all("a")]


def test_path_language_prefix_sets_the_locale(test_app: Engine):
    response = test_app.test_client().get("/pl/blog/page/test")
    assert response.status_code == 200
    assert _language_indicator(response) == "pl"


def test_accept_language_does_not_change_the_locale(test_app: Engine):
    response = test_app.test_client().get("/blog/page/test", headers={"Accept-Language": "pl"})
    assert _language_indicator(response) == "en"


def test_anonymous_page_view_sets_no_cookie(test_app: Engine):
    response = test_app.test_client().get("/pl/blog/page/test")
    assert "Set-Cookie" not in response.headers


@pytest.mark.parametrize("path", ["/en/", "/xx/", "/en/blog/page/test"])
def test_only_path_languages_have_a_prefix(test_app: Engine, path: str):
    assert test_app.test_client().get(path).status_code == 404


def test_url_for_follows_the_language_of_the_request(test_app: Engine):
    with test_app.test_request_context("/pl/blog/"):
        assert url_for("blog.get_post", post_slug="x") == "/pl/blog/x"
        assert url_for("static", filename="blog.css") == "/static/blog.css"
        assert url_for("home_page", lang_code=None) == "/"
    with test_app.test_request_context("/blog/"):
        assert url_for("blog.get_post", post_slug="x") == "/blog/x"


def _post(slug: str, title: str, language: str) -> dict[str, Any]:
    return {
        "title": title,
        "slug": slug,
        "language": language,
        "excerpt": "excerpt",
        "author": "author",
        "tags": [],
        "contentInMarkdown": title,
        "date": "2021-02-19",
        "comments": [],
    }


def _build_bilingual_blog_test_app() -> Engine:
    return _build_home_page_test_app(
        {
            "posts": [
                _post("english-post", "English post", "en"),
                _post("polski-wpis", "Polski wpis", "pl"),
            ]
        },
        languages=_BILINGUAL_LANGUAGES,
        default_language="en",
    )


def test_path_language_blog_lists_its_posts_under_its_prefix():
    response = _build_bilingual_blog_test_app().test_client().get("/pl/blog/")
    assert response.status_code == 200
    assert b"Polski wpis" in response.data
    assert b"English post" not in response.data
    hrefs = _link_hrefs(response)
    assert "/pl/blog/polski-wpis" in hrefs
    assert "/pl/" in hrefs


def test_default_language_blog_links_are_unprefixed():
    response = _build_bilingual_blog_test_app().test_client().get("/blog/")
    assert b"English post" in response.data
    assert b"Polski wpis" not in response.data
    hrefs = _link_hrefs(response)
    assert "/blog/english-post" in hrefs
    assert "/" in hrefs


def test_path_language_post_submits_comments_under_its_prefix():
    response = _build_bilingual_blog_test_app().test_client().get("/pl/blog/polski-wpis")
    assert response.status_code == 200
    form = BeautifulSoup(response.data, "html.parser").find("form")
    assert isinstance(form, Tag)
    assert form.get("action") == "/pl/blog/polski-wpis"


def test_path_language_feed_links_to_prefixed_posts():
    response = _build_bilingual_blog_test_app().test_client().get("/pl/blog/feed")
    assert response.status_code == 200
    assert b"http://localhost/pl/blog/polski-wpis" in response.data


def _build_three_language_test_app(use_www: bool = False) -> Engine:
    config = Config.model_validate(
        {
            "APP_NAME": "testingApp",
            "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
            "USE_WWW": use_www,
            "BLOG_PREFIX": "/blog",
            "DEFAULT_LANGUAGE": "en",
            "LANGUAGES": {
                "en": {"name": "English", "flag": "gb", "country": "GB", "domain": "example.com"},
                "pl": {"name": "polski", "flag": "pl", "country": "PL"},
                "de": {"name": "Deutsch", "flag": "de", "country": "DE", "domain": "example.de"},
            },
            "DB": {"TYPE": "json", "DATA": {"site_content": {"pages": _ABOUT_PAGES}}},
        }
    )
    return create_app_from_config(config)


@pytest.mark.parametrize(("host", "status"), [("example.com", 200), ("example.de", 404)])
def test_path_languages_are_served_on_the_main_host_only(host: str, status: int):
    app = _build_three_language_test_app()
    response = app.test_client().get("/pl/blog/page/about", headers={"Host": host})
    assert response.status_code == status


@pytest.mark.parametrize("host", ["example.com", "example.de"])
def test_hreflang_links_point_at_each_language_home(host: str):
    app = _build_three_language_test_app()
    response = app.test_client().get("/blog/page/about", headers={"Host": host})
    assert _hreflang_urls(response) == {
        "en": "http://example.com/",
        "pl": "http://example.com/pl/",
        "de": "http://example.de/",
        "x-default": "http://example.com/",
    }


def test_www_host_resolves_to_its_language():
    app = _build_three_language_test_app(use_www=True)
    response = app.test_client().get("/blog/page/about", headers={"Host": "www.example.de"})
    assert _language_indicator(response) == "de"
    assert _hreflang_urls(response)["pl"] == "http://www.example.com/pl/"


@pytest.mark.parametrize(("host", "lists_pl"), [("example.com", True), ("example.de", False)])
def test_sitemap_lists_path_languages_on_the_main_host_only(host: str, lists_pl: bool):
    app = _build_three_language_test_app()
    response = app.test_client().get("/sitemap.xml", headers={"Host": host})
    assert f"http://{host}/blog/" in response.text
    assert (f"http://{host}/pl/blog/" in response.text) is lists_pl
