import logging

import pytest

from platzky.config import Config
from platzky.platzky import create_app_from_config

CONTENT_URLS = ["/blog/slug", "/blog/page/slug"]


def _app(content: str):
    post = {
        "author": "author",
        "slug": "slug",
        "title": "title",
        "language": "en",
        "contentInMarkdown": content,
        "excerpt": "excerpt",
    }
    config = Config.model_validate(
        {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {
                "TYPE": "json",
                "DATA": {"site_content": {"posts": [post], "pages": [post]}, "plugins": {}},
            },
        }
    )
    return create_app_from_config(config)


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_malformed_shortcode_shows_the_content_error_page(
    url: str, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level(logging.ERROR):
        response = _app('[link url="/x"]never closed').test_client().get(url)
    assert response.status_code == 500
    assert "Please contact the site administrator." in response.get_data(as_text=True)
    assert "[link] is never closed" in caplog.text


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_wellformed_content_renders(url: str):
    response = _app('[link url="/x"]fine[/link]').test_client().get(url)
    assert response.status_code == 200
