import secrets
from collections.abc import Mapping
from datetime import date

from flask import Blueprint, Flask
from flask_wtf.csrf import CSRFProtect

from platzky.language_routing import SiteLanguages
from platzky.seo import seo
from platzky.sitemap import SitemapEntries, SitemapEntry, single_url

_ENGLISH_ONLY = SiteLanguages(domains={"en": None}, default="en")
_ENGLISH_AND_UKRAINIAN = SiteLanguages(domains={"en": None, "uk": None}, default="en")


def _make_seo_app(
    blueprints: list[Blueprint] | None = None,
    sitemap_entries: Mapping[str, SitemapEntries] | None = None,
    languages: SiteLanguages = _ENGLISH_ONLY,
    sitemap_excluded_prefixes: list[str] | None = None,
) -> Flask:
    """Build a minimal Flask app with the SEO blueprint and the given blueprints."""
    config = {"SEO_PREFIX": "/prefix", "SITEMAP_EXCLUDED_PREFIXES": sitemap_excluded_prefixes}
    app = Flask(__name__)
    app.config.update({"TESTING": True, "SECRET_KEY": secrets.token_hex()})
    CSRFProtect(app)
    for blueprint in blueprints or []:
        app.register_blueprint(blueprint)
    app.register_blueprint(seo.create_seo_blueprint(config, languages, sitemap_entries or {}))
    return app


def _books_blueprint() -> Blueprint:
    """A blueprint with a fixed page, a page per book, and both also under /uk/."""
    books = Blueprint("books", __name__)

    @books.route("/books/")
    @books.route("/<any('uk'):lang_code>/books/")
    def index(lang_code: str | None = None) -> str:
        return lang_code or "books"

    @books.route("/books/<isbn>")
    @books.route("/<any('uk'):lang_code>/books/<isbn>")
    def book(isbn: str, lang_code: str | None = None) -> str:
        return f"{isbn} {lang_code or ''}"

    @books.route("/about")
    def about() -> str:
        return "about"

    return books


def _books_in(lang: str) -> list[SitemapEntry]:
    isbn = {"en": "978-0261102217", "uk": "978-6177585"}.get(lang, "978-3608939842")
    return [SitemapEntry({"isbn": isbn}, date(1937, 9, 21))]


def _sitemap(app: Flask) -> str:
    return app.test_client().get("/prefix/sitemap.xml").text


def test_robots_txt():
    app = _make_seo_app()
    app.config.update({"DEBUG": True})
    response = app.test_client().get("/prefix/robots.txt")
    assert response.status_code == 200
    assert "Sitemap: https://localhost/sitemap.xml" in response.text


def test_sitemap_lists_each_entry_with_its_lastmod():
    app = _make_seo_app([_books_blueprint()], {"books.book": _books_in})
    sitemap = _sitemap(app)
    assert "<loc>http://localhost/books/978-0261102217</loc>" in sitemap
    assert "<lastmod>1937-09-21</lastmod>" in sitemap


def test_sitemap_lists_a_route_without_variables_without_lastmod():
    app = _make_seo_app([_books_blueprint()], {"books.about": single_url})
    sitemap = _sitemap(app)
    assert "<loc>http://localhost/about</loc>" in sitemap
    assert "<lastmod>" not in sitemap


def test_sitemap_leaves_out_routes_not_registered_for_it():
    app = _make_seo_app([_books_blueprint()], {"books.about": single_url})
    assert "/books/" not in _sitemap(app)


def test_sitemap_lists_localized_routes_in_every_language_served_on_the_host():
    entries = {"books.index": single_url, "books.book": _books_in}
    sitemap = _sitemap(_make_seo_app([_books_blueprint()], entries, _ENGLISH_AND_UKRAINIAN))
    assert "http://localhost/books/</loc>" in sitemap
    assert "http://localhost/uk/books/</loc>" in sitemap
    assert "http://localhost/books/978-0261102217" in sitemap
    assert "http://localhost/uk/books/978-6177585" in sitemap


def test_sitemap_on_a_language_domain_lists_only_that_language():
    # The test client's host is localhost, so here it is German's own domain.
    german_domain = SiteLanguages(
        domains={"en": "example.com", "uk": None, "de": "localhost"}, default="en"
    )
    entries = {"books.book": _books_in}
    sitemap = _sitemap(_make_seo_app([_books_blueprint()], entries, german_domain))
    assert "http://localhost/books/978-3608939842" in sitemap
    assert "/uk/" not in sitemap


def test_sitemap_lists_a_route_without_a_language_version_once():
    entries = {"books.about": single_url}
    sitemap = _sitemap(_make_seo_app([_books_blueprint()], entries, _ENGLISH_AND_UKRAINIAN))
    assert sitemap.count("/about</loc>") == 1


def test_sitemap_leaves_out_urls_under_an_excluded_prefix():
    app = _make_seo_app(
        [_books_blueprint()],
        {"books.book": _books_in, "books.about": single_url},
        sitemap_excluded_prefixes=["/books/"],
    )
    sitemap = _sitemap(app)
    assert "/books/" not in sitemap
    assert "http://localhost/about" in sitemap
