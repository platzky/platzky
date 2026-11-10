from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

import pytest
from flask import render_template_string

from platzky.config import Config
from platzky.engine import Engine
from platzky.platzky import create_app_from_config

CONTENT_URLS = ["/blog/slug", "/blog/page/slug"]
_CONTENT = {
    "author": "author",
    "slug": "slug",
    "title": "title",
    "contentInMarkdown": "content",
    "excerpt": "excerpt",
}


def _app(site_config: Mapping[str, Any] = MappingProxyType({})) -> Engine:
    config = Config.model_validate(
        {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/blog",
            "DB": {
                "TYPE": "json",
                "DATA": {
                    "site_config": dict(site_config),
                    "blog": {"posts": [_CONTENT], "pages": [_CONTENT]},
                },
            },
        }
    )
    return create_app_from_config(config)


def _footer(content: str, **presentation: bool) -> dict[str, Any]:
    """The site config with an English footer."""
    return {"localized_content": {"en": {"footer": {"content": content, **presentation}}}}


def _html(app: Engine, url: str) -> str:
    return app.test_client().get(url).get_data(as_text=True)


def test_no_footer_configured_renders_no_footer_row():
    assert 'id="footer-row"' not in _html(_app(), "/blog/slug")


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_footer_is_rendered_on_posts_and_pages(url: str):
    html = _html(_app(_footer('[link url="/x"]Site footer[/link]')), url)
    assert 'id="footer-row"' in html
    assert 'href="/x"' in html
    assert "Site footer" in html
    assert "[link" not in html


def test_footer_renders_markdown():
    html = _html(_app(_footer('**Bold** and [link url="/x"]a *link*[/link]')), "/blog/slug")
    assert "<p><strong>Bold</strong> and" in html
    assert "<em>link</em>" in html


def test_footer_of_the_page_language_is_rendered():
    site_config = {
        "localized_content": {
            "en": {"footer": {"content": "Footer"}},
            "pl": {"footer": {"content": "Stopka"}},
        }
    }
    html = _html(_app(site_config), "/blog/slug")
    assert "Footer" in html
    assert "Stopka" not in html


def test_template_footer_block_replaces_the_whole_footer():
    """The outer block owns the region: overriding it drops the <footer> and the toggle."""
    app = _app(_footer("Site footer", collapsible=True))
    template = '{% extends "base.html" %}{% block footer %}<p>Mine</p>{% endblock %}'
    with app.test_request_context():
        html = render_template_string(template)
    assert "<p>Mine</p>" in html
    assert "Site footer" not in html
    assert 'id="footer-row"' not in html
    assert "<details" not in html


@pytest.mark.parametrize("presentation", [{}, {"collapsible": False}])
def test_footer_is_not_collapsible_unless_configured(presentation: dict[str, bool]):
    html = _html(_app(_footer("Site footer", **presentation)), "/blog/slug")
    assert "Site footer" in html
    assert "<details" not in html


def test_collapsible_footer_starts_open_with_content_inside():
    html = _html(_app(_footer("Site footer", collapsible=True)), "/blog/slug")
    details = html[html.index("<details open>") : html.index("</details>")]
    assert '<summary class="footer-toggle">' in details
    assert "Site footer" in details


def test_footer_background_is_the_theme_secondary_color():
    html = _html(_app({**_footer("Site footer"), "secondary_color": "goldenrod"}), "/blog/slug")
    rule = html[html.index("#footer-row") :]
    assert "goldenrod" in rule[: rule.index("}")]


@pytest.mark.parametrize(
    ("url", "status"),
    [("/blog/slug", 200), ("/blog/page/slug", 200), ("/blog/no-such-page", 404)],
)
def test_malformed_footer_hides_footer_instead_of_breaking_the_page(url: str, status: int):
    response = _app(_footer('[link url="/x"]Never closed')).test_client().get(url)
    html = response.get_data(as_text=True)
    assert response.status_code == status
    assert 'id="footer-row"' not in html
    assert "Never closed" not in html
