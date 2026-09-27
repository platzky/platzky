import secrets
from collections.abc import Mapping
from datetime import date

from flask import Blueprint, Flask
from flask_wtf.csrf import CSRFProtect

from platzky.language_routing import SiteLanguages
from platzky.seo import seo
from platzky.sitemap import SitemapEntries, SitemapEntry, UrlFor, single_url

_ENGLISH_ONLY = SiteLanguages(domains={"en": None}, default="en")
_ENGLISH_AND_UKRAINIAN = SiteLanguages(domains={"en": None, "uk": None}, default="en")


def _make_seo_app(
    sitemap_entries: Mapping[str, SitemapEntries] | None = None,
    languages: SiteLanguages = _ENGLISH_ONLY,
    sitemap_excluded_prefixes: list[str] | None = None,
) -> Flask:
    """Build a minimal Flask app with the books routes and the SEO blueprint."""
    config = {"SEO_PREFIX": "/prefix", "SITEMAP_EXCLUDED_PREFIXES": sitemap_excluded_prefixes}
    app = Flask(__name__)
    app.config.update({"TESTING": True, "SECRET_KEY": secrets.token_hex()})
    CSRFProtect(app)
    app.register_blueprint(_books_blueprint())
    app.register_blueprint(seo.create_seo_blueprint(config, languages, sitemap_entries or {}))
    return app


def _books_blueprint() -> Blueprint:
    """A page per book, also under /uk/, and an about page in one language only."""
    books = Blueprint("books", __name__)

    @books.route("/books/<isbn>")
    @books.route("/<any('uk'):lang_code>/books/<isbn>")
    def book(isbn: str, lang_code: str | None = None) -> str:
        return f"{isbn} {lang_code or ''}"

    @books.route("/about")
    def about() -> str:
        return "about"

    return books


def _books_in(lang: str, url: UrlFor) -> list[SitemapEntry]:
    isbn = {"en": "978-0261102217", "uk": "978-6177585"}.get(lang, "978-3608939842")
    return [SitemapEntry(url(isbn=isbn), date(1937, 9, 21))]


def _sitemap(app: Flask) -> str:
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
    german_domain = SiteLanguages(
        domains={"en": "example.com", "uk": None, "de": "localhost"}, default="en"
    )
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


def test_sitemap_leaves_out_urls_under_an_excluded_prefix():
    app = _make_seo_app(
        {"books.book": _books_in, "books.about": single_url},
        sitemap_excluded_prefixes=["/books/"],
    )
    sitemap = _sitemap(app)
    assert "/books/" not in sitemap
    assert "http://localhost/about" in sitemap
