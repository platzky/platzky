from typing import Any

import pytest
from flask import render_template_string

from platzky.config import Config
from platzky.engine import Engine
from platzky.platzky import create_app_from_config

CONTENT_URLS = ["/blog/slug", "/blog/page/slug"]


def _content(**overrides: object) -> dict[str, Any]:
    return {
        "author": "author",
        "slug": "slug",
        "title": "title",
        "language": "en",
        "contentInMarkdown": "content",
        "excerpt": "excerpt",
        **overrides,
    }


def _app(site_footer: dict[str, str] | None = None, **content_overrides: object) -> Engine:
    site_content: dict[str, Any] = {
        "posts": [_content(**content_overrides)],
        "pages": [_content(**content_overrides)],
    }
    if site_footer is not None:
        site_content["footer"] = site_footer
    config = Config.model_validate(
        {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "DB": {"TYPE": "json", "DATA": {"site_content": site_content, "plugins": {}}},
        }
    )
    return create_app_from_config(config)


def _html(app: Engine, url: str) -> str:
    return app.test_client().get(url).get_data(as_text=True)


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_no_footer_configured_renders_no_footer_row(url: str):
    assert 'id="footer-row"' not in _html(_app(), url)


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_site_footer_renders_builtin_shortcodes(url: str):
    html = _html(_app(site_footer={"en": '[link url="/x"]Site footer[/link]'}), url)
    assert 'id="footer-row"' in html
    assert 'href="/x"' in html
    assert "Site footer" in html
    assert "[link" not in html


def test_site_footer_is_looked_up_per_language():
    assert 'id="footer-row"' not in _html(_app(site_footer={"pl": "Stopka"}), "/blog/slug")


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_content_footer_replaces_site_footer(url: str):
    html = _html(_app(site_footer={"en": "Site footer"}, footer="Own footer"), url)
    assert "Own footer" in html
    assert "Site footer" not in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_empty_content_footer_hides_site_footer(url: str):
    html = _html(_app(site_footer={"en": "Site footer"}, footer=""), url)
    assert 'id="footer-row"' not in html
    assert "Site footer" not in html


def test_template_footer_block_beats_site_footer():
    app = _app(site_footer={"en": "Site footer"})
    template = '{% extends "base.html" %}{% block footer %}From template{% endblock %}'
    with app.test_request_context():
        html = render_template_string(template)
    assert "From template" in html
    assert "Site footer" not in html
