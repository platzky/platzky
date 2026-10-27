from typing import Any

import pytest
from flask import Flask

from platzky.config import Config
from platzky.platzky import create_app_from_config


def build_test_app(site_content_overrides: dict[str, Any] | None = None) -> Flask:
    """Build the standard test app, optionally overriding `site_content` fields.

    An override value of `None` removes that field from the site content.
    """
    config_data: dict[str, Any] = {
        "APP_NAME": "testing App Name",
        "SECRET_KEY": "secret",
        "USE_WWW": False,
        "BLOG_PREFIX": "/blog",
        "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
        "DEFAULT_LANGUAGE": "en",
        "LANGUAGES": {
            "en": {"name": "English", "flag": "uk", "country": "GB"},
            "pl": {"name": "Polski", "flag": "pl", "country": "PL"},
        },
        "DB": {
            "TYPE": "json",
            "DATA": {
                "site_content": {
                    "logo_url": "https://example.com/logo.png",
                    "pages": [
                        {
                            "title": "test",
                            "slug": "test",
                            "excerpt": "excerpt",
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
                        },
                        {
                            "title": "test",
                            "slug": "test",
                            "excerpt": "excerpt",
                            "contentInMarkdown": "",
                            "contentInRichText": "test pl",
                            "comments": [],
                            "tags": [],
                            "coverImage": {
                                "alternateText": "text which is alternative",
                                "url": "https://media.graphcms.com/XvmCDUjYTIq4c9wOIseo",
                            },
                            "language": "en",
                            "date": "2021-01-01",
                            "author": "author",
                        },
                    ],
                },
            },
        },
    }
    site_content = config_data["DB"]["DATA"]["site_content"]
    for key, value in (site_content_overrides or {}).items():
        if value is None:
            site_content.pop(key, None)
        else:
            site_content[key] = value
    config = Config.model_validate(config_data)
    app = create_app_from_config(config)
    assert isinstance(app, Flask)
    return app


@pytest.fixture
def test_app():
    return build_test_app()
