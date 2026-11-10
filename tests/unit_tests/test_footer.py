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


def _app(
    footer: dict[str, Any] | None = None,
    footer_lang: str = "en",
    secondary_color: str | None = None,
    **content_overrides: object,
) -> Engine:
    site_content: dict[str, Any] = {
        "posts": [_content(**content_overrides)],
        "pages": [_content(**content_overrides)],
    }
    if secondary_color is not None:
        site_content["secondary_color"] = secondary_color
    if footer is not None:
        site_content["localized_content"] = {footer_lang: {"footer": footer}}
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
def test_site_footer_renders_markdown(url: str):
    html = _html(_app(footer={"content": '**Bold** and [link url="/x"]a *link*[/link]'}), url)
    assert "<p><strong>Bold</strong> and" in html
    assert 'href="/x"' in html
    assert "<em>link</em>" in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_site_footer_renders_builtin_shortcodes(url: str):
    html = _html(_app(footer={"content": '[link url="/x"]Site footer[/link]'}), url)
    assert 'id="footer-row"' in html
    assert 'href="/x"' in html
    assert "Site footer" in html
    assert "[link" not in html


def test_site_footer_is_looked_up_per_language():
    assert 'id="footer-row"' not in _html(
        _app(footer={"content": "Stopka"}, footer_lang="pl"), "/blog/slug"
    )


def test_template_footer_block_replaces_the_whole_footer():
    """The outer block owns the region: overriding it drops the <footer> and the toggle."""
    app = _app(footer={"content": "Site footer", "collapsible": True})
    template = '{% extends "base.html" %}{% block footer %}<p>Mine</p>{% endblock %}'
    with app.test_request_context():
        html = render_template_string(template)
    assert "<p>Mine</p>" in html
    assert "Site footer" not in html
    assert 'id="footer-row"' not in html
    assert "<details" not in html


@pytest.mark.parametrize("collapsible", [{}, {"collapsible": False}])
def test_footer_is_not_collapsible_unless_configured(collapsible: dict[str, bool]):
    html = _html(_app(footer={"content": "Site footer", **collapsible}), "/blog/slug")
    assert "Site footer" in html
    assert "<details" not in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_collapsible_footer_starts_open_with_content_inside(url: str):
    html = _html(_app(footer={"content": "Site footer", "collapsible": True}), url)
    details = html[html.index("<details open>") : html.index("</details>")]
    assert '<summary class="footer-toggle">' in details
    assert "Site footer" in details


def test_footer_background_is_the_theme_secondary_color():
    html = _html(_app(footer={"content": "Site footer"}, secondary_color="goldenrod"), "/blog/slug")
    rule = html[html.index("#footer-row") :]
    assert "goldenrod" in rule[: rule.index("}")]


@pytest.mark.parametrize("url", [*CONTENT_URLS, "/blog/no-such-page"])
def test_malformed_site_footer_hides_footer_instead_of_breaking_the_page(url: str):
    app = _app(footer={"content": '[link url="/x"]Never closed'})
    response = app.test_client().get(url)
    html = response.get_data(as_text=True)
    assert response.status_code in (200, 404)
    assert 'id="footer-row"' not in html
    assert "Never closed" not in html
