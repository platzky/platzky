import pytest
from bs4 import BeautifulSoup, Tag

from platzky.config import Config
from platzky.platzky import create_app_from_config
from tests.unit_tests.fake_app import test_app

test_app = test_app


def test_babel_gets_proper_directories(test_app):
    with test_app.app_context():
        assert "/some/fake/dir" in list(test_app.babel.domain_instance.translation_directories)


def test_logo_has_set_src(test_app):
    app = test_app.test_client()
    response = app.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    found_image = soup.find("img")
    assert isinstance(found_image, Tag)
    assert found_image.get("src") is not None
    assert found_image.get("src") == "https://example.com/logo.png"


def test_if_name_is_shown_if_there_is_no_logo(test_app):
    test_app.db.data["site_content"].pop("logo_url")
    app = test_app.test_client()
    response = app.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.find("img") is None
    branding = soup.find("a", {"class": "navbar-brand"})
    assert branding is not None
    assert branding.get_text() == "testing App Name"


def test_favicon_is_applied(test_app):
    test_app.db.data["site_content"]["favicon_url"] = "https://example.com/favicon.ico"
    app = test_app.test_client()
    response = app.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    found_ico = soup.find("link", rel="icon")
    assert found_ico is not None
    assert isinstance(found_ico, Tag)
    assert found_ico.get("href") is not None
    assert found_ico.get("href") == "https://example.com/favicon.ico"


def test_notifier(test_app):
    engine = test_app
    notifier_msg = None

    def notifier(message):
        nonlocal notifier_msg
        notifier_msg = message

    engine.add_notifier(notifier)
    engine.notify("test")
    assert notifier_msg == "test"


@pytest.mark.parametrize("content_type", ["body", "head"])
def test_dynamic_content(test_app, content_type):
    def add_dynamic_element(engine, content):
        getattr(engine, f"add_dynamic_{content_type}")(content)

    def get_content_text(response, content_type):
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
def test_www_redirects(test_app, use_www):
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


def test_that_default_page_title_is_app_name(test_app):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.title is not None
    assert soup.title.string == "testing App Name"


@pytest.mark.parametrize(
    "tag, subtag, value", [("link", "hreflang", "en"), ("html", "lang", "en-GB")]
)
def test_that_tag_has_proper_value(test_app, tag, subtag, value):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert getattr(soup, tag) is not None
    assert getattr(soup, tag).get(subtag) == value


def test_that_logo_has_proper_alt_text(test_app):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    logo_img = soup.find("img", class_="logo")
    assert isinstance(logo_img, Tag)
    assert logo_img.get("alt") == "testing App Name logo"


def test_that_logo_link_has_proper_aria_label_text(test_app):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    logo_link = soup.find("a", class_="navbar-brand")
    assert isinstance(logo_link, Tag)
    assert logo_link.get("aria-label") == "Link to home page"


def test_that_language_menu_has_proper_code(test_app):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    language_menu = soup.find("span", class_="language-indicator-text")
    assert isinstance(language_menu, Tag)
    assert language_menu.get_text() == "en"


def test_that_language_switch_has_proper_aria_label_text(test_app):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    logo_link = soup.find("button", id="languages-menu")
    assert isinstance(logo_link, Tag)
    assert (
        logo_link.get("aria-label")
        == "Language switch icon, used to change the language of the website"
    )


def test_that_page_has_proper_html_lang_attribute(test_app):
    response = test_app.test_client().get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.html and soup.html.get("lang") == "en-GB"


def test_add_login_method(test_app):
    def sample_login_method():
        return "Login Method"

    test_app.add_login_method(sample_login_method)
    assert sample_login_method in test_app.login_methods

    app = test_app.test_client()
    response = app.get("/admin/", follow_redirects=True)

    assert response.status_code == 200
    assert b"Login Method" in response.data
