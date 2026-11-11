import logging
from collections.abc import Mapping
from datetime import date

import pytest
from flask import Blueprint
from flask_wtf.csrf import CSRFProtect
from markupsafe import escape

from platzky.config import Config
from platzky.db.db_loader import get_db
from platzky.engine import Engine
from platzky.seo import seo
from platzky.sitemap import SitemapEntry, SitemapProvider, UrlFor, single_url

_ENGLISH_ONLY: Mapping[str, str | None] = {"en": None}
_ENGLISH_AND_UKRAINIAN: Mapping[str, str | None] = {"en": None, "uk": None}


def _make_seo_app(
    sitemap_providers: Mapping[str, SitemapProvider] | None = None,
    domains: Mapping[str, str | None] = _ENGLISH_ONLY,
    sitemap_excluded_prefixes: list[str] | None = None,
) -> Engine:
    """Build an Engine with the books routes and the SEO blueprint.

    Args:
        sitemap_providers: Sitemap providers of the books routes, by endpoint.
        domains: The site's languages mapped to their own domain, if any; the first is the default.
        sitemap_excluded_prefixes: URL prefixes the sitemap leaves out.
    """
    config = Config.model_validate(
        {
            "APP_NAME": "testingApp",
            "SECRET_KEY": "secret",  # NOSONAR - hardcoded secret acceptable in tests
            "SEO_PREFIX": "/prefix",
            "SITEMAP_EXCLUDED_PREFIXES": sitemap_excluded_prefixes or [],
            "DEFAULT_LANGUAGE": next(iter(domains)),
            "LANGUAGES": {
                code: {"name": code, "flag": code, "country": code.upper(), "domain": domain}
                for code, domain in domains.items()
            },
            "DB": {"TYPE": "json", "DATA": {"site_config": {}}},
        }
    )
    app = Engine(config, get_db(config.db), __name__)
    app.config["TESTING"] = True
    CSRFProtect(app)
    app.register_blueprint(_books_blueprint())
    app.register_blueprint(
        seo.create_seo_blueprint(
            app.config, config.language_routing, sitemap_providers or {}, app.url_for_language
        )
    )
    return app


def _books_blueprint() -> Blueprint:
    """A page per book in every language, and an about page in one language only."""
    books = Blueprint("books", __name__)

    @books.route("/books/<isbn>", multilang=True)
    def book(isbn: str) -> str:
        return escape(isbn)

    @books.route("/about")
    def about() -> str:
        return "about"

    return books


def _books_in(lang: str, url: UrlFor) -> list[SitemapEntry]:
    isbn = {"en": "978-0261102217", "uk": "978-6177585"}.get(lang, "978-3608939842")
    return [SitemapEntry(url(isbn=isbn), date(1937, 9, 21))]


def _sitemap(app: Engine) -> str:
    return app.test_client().get("/prefix/sitemap.xml").text


def test_robots_txt():
    app = _make_seo_app()
    app.config.update({"DEBUG": True})
    response = app.test_client().get("/prefix/robots.txt")
    assert response.status_code == 200
    assert "Sitemap: https://localhost/sitemap.xml" in response.text


def test_sitemap_lists_each_entry_with_its_lastmod():
    sitemap = _sitemap(_make_seo_app({"books.book": _books_in}))
    assert "<loc>http://localhost/books/978-0261102217</loc>" in sitemap
    assert "<lastmod>1937-09-21</lastmod>" in sitemap


def test_sitemap_leaves_out_lastmod_when_unknown():
    sitemap = _sitemap(_make_seo_app({"books.about": single_url}))
    assert "<loc>http://localhost/about</loc>" in sitemap
    assert "<lastmod>" not in sitemap


def test_sitemap_leaves_out_routes_not_registered_for_it():
    assert "/books/" not in _sitemap(_make_seo_app({"books.about": single_url}))


def test_sitemap_asks_a_localized_route_for_every_language_served_on_the_host():
    sitemap = _sitemap(_make_seo_app({"books.book": _books_in}, _ENGLISH_AND_UKRAINIAN))
    assert "http://localhost/books/978-0261102217" in sitemap
    assert "http://localhost/uk/books/978-6177585" in sitemap


def test_sitemap_on_a_language_domain_asks_only_for_that_language():
    # The test client's host is localhost, so here it is German's own domain.
    german_domain = {"en": "example.com", "uk": None, "de": "localhost"}
    sitemap = _sitemap(_make_seo_app({"books.book": _books_in}, german_domain))
    assert "http://localhost/books/978-3608939842" in sitemap
    assert "978-0261102217" not in sitemap
    assert "/uk/" not in sitemap


def test_sitemap_asks_a_route_without_a_language_version_only_once():
    asked: list[str] = []

    def about_in(lang: str, url: UrlFor) -> list[SitemapEntry]:
        asked.append(lang)
        return single_url(lang, url)

    _sitemap(_make_seo_app({"books.about": about_in}, _ENGLISH_AND_UKRAINIAN))
    assert asked == ["en"]


def test_sitemap_leaves_out_urls_under_an_excluded_prefix_in_every_language():
    app = _make_seo_app(
        {"books.book": _books_in, "books.about": single_url},
        _ENGLISH_AND_UKRAINIAN,
        sitemap_excluded_prefixes=["/books/"],
    )
    sitemap = _sitemap(app)
    assert "/books/" not in sitemap
    assert "http://localhost/about" in sitemap


def _misspelled_books(_lang: str, url: UrlFor) -> list[SitemapEntry]:
    return [SitemapEntry(url(isnb="978-0261102217"))]


@pytest.mark.parametrize("provider", [single_url, _misspelled_books])
def test_sitemap_leaves_out_a_route_whose_urls_cannot_be_built(
    caplog: pytest.LogCaptureFixture, provider: SitemapProvider
):
    app = _make_seo_app({"books.book": provider, "books.about": single_url})
    with caplog.at_level(logging.WARNING, logger="platzky.seo.seo"):
        sitemap = _sitemap(app)
    assert "The sitemap leaves out 'books.book'" in caplog.text
    assert "/books/" not in sitemap
    assert "http://localhost/about" in sitemap
