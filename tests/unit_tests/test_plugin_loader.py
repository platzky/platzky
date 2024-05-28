from platzky.config import Config
import copy
from platzky.platzky import create_app_from_config


def test_plugin_loader():
    without_plugin_config_data = {
        "APP_NAME": "testingApp",
        "SECRET_KEY": "secret",
        "USE_WWW": False,
        "BLOG_PREFIX": "/",
        "TRANSLATION_DIRECTORIES": ["/some/fake/dir"],
        "DB": {
            "TYPE": "json",
            "DATA": {
                "site_content": {
                    "pages": [
                        {
                            "title": "test",
                            "slug": "test",
                            "excerpt": "test",
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

    with_plugin_config_data = copy.deepcopy(without_plugin_config_data)
    with_plugin_config_data["DB"]["DATA"]["plugins"] = [
        {"name": "redirections", "config": {"/page/test": "/page/test2"}}
    ]

    config_without_plugin = Config.model_validate(without_plugin_config_data)
    config_with_plugin = Config.model_validate(with_plugin_config_data)

    app_without_plugin = create_app_from_config(config_without_plugin)
    app_with_plugin = create_app_from_config(config_with_plugin)

    response = app_without_plugin.test_client().get(
        "/page/test", follow_redirects=False
    )
    response2 = app_with_plugin.test_client().get("/page/test", follow_redirects=False)

    assert response.status_code == 200
    assert response.location is None
    assert response2.status_code == 301
    assert response2.location == "/page/test2"
