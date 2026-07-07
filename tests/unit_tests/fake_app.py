import pytest
from flask import Flask

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
        "LANGUAGES": {
            "en": {"name": "English", "flag": "uk", "domain": "localhost", "country": "GB"},
            "pl": {"name": "Polski", "flag": "pl", "domain": "localhost", "country": "PL"},
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
    config = Config.model_validate(config_data)
    app = create_app_from_config(config)
    assert isinstance(app, Flask)
    return app
