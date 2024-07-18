import pytest
from flask import Flask
from bs4 import BeautifulSoup
from platzky.config import Config
from platzky.platzky import create_app_from_config


@pytest.fixture
def test_app():
    config_data = {
        "APP_NAME": "testing App Name",
        "SECRET_KEY": "secret",
        "USE_WWW": False,
        "BLOG_PREFIX": "/blog",
        "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
        "DB": {
            "TYPE": "json",
            "DATA": {
                "site_content": {
                    "pages": [
                        {
                            "title": "test",
                            "slug": "test",
                            "contentInMarkdown": "",
                            "contentInRichText": "test",
                            "comments": [],
                            "tags": [],
                            "coverImage": {
                                "alternateText": "text which is alternative",
                                "url": "https://media.graphcms.com/XvmCDUjYTIq4c9wOIseo",
                            },
                            "language": "en",
                            "date": "2021-01-01",
                            "author": "author",
                        }
                    ],
                }
            },
        },
    }
    config = Config.model_validate(config_data)
    app = create_app_from_config(config)
    assert isinstance(app, Flask)
    return app


def test_babel_gets_proper_directories(test_app):
    with test_app.app_context():
        assert list(test_app.babel.domain_instance.translation_directories) == [
            "/some/fake/dir"
        ]


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

    engine = test_app
    add_dynamic_element(engine, "test1")
    add_dynamic_element(engine, "test2")
    app = engine.test_client()
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
                    "pages": [
                        {"title": "test", "slug": "test", "contentInMarkdown": "test"}
                    ],
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
    assert soup.title.string == "testing App Name"
