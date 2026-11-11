from platzky.config import Config
from platzky.engine import Engine
from platzky.platzky import create_app_from_config

FONT_URL = "https://fonts.example/poppins.css"


POST = {
    "author": "author",
    "slug": "slug",
    "title": "title",
    "language": "en",
    "contentInMarkdown": "content",
    "excerpt": "excerpt",
}


def _app(**site_config: object) -> Engine:
    config = Config.model_validate(
        {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {
                "TYPE": "json",
                "DATA": {"site_config": site_config, "blog": {"posts": [POST]}, "plugins": {}},
            },
        }
    )
    return create_app_from_config(config)


def test_configured_font_renders_stylesheet_link_and_font_family():
    response = _app(font={"name": "Poppins", "url": FONT_URL}).test_client().get("/blog/slug")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert f'<link rel="stylesheet" href="{FONT_URL}">' in html
    assert "body{font-family:Poppins}" in html


def test_unset_font_renders_no_empty_stylesheet_link_or_font_family():
    response = _app().test_client().get("/blog/slug")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<link rel="stylesheet" href="">' not in html
    assert "body{font-family:}" not in html
