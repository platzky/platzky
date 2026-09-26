import secrets
from functools import partial
from unittest.mock import MagicMock

from flask import Blueprint, Flask
from flask_wtf.csrf import CSRFProtect

from platzky.language_routing import SiteLanguages
from platzky.models import Comment, Image, Post
from platzky.seo import seo

_ENGLISH_ONLY = SiteLanguages(domains={"en": None}, default="en")
_ENGLISH_AND_UKRAINIAN = SiteLanguages(domains={"en": None, "uk": None}, default="en")


def _make_test_flask_app() -> Flask:
    app = Flask(__name__)
    app.config.update({"TESTING": True, "SECRET_KEY": secrets.token_hex()})
    CSRFProtect(app)
    return app


def _make_seo_app(
    extra_blueprints: list[Blueprint] | None = None,
    sitemap_excluded_prefixes: list[str] | None = None,
    languages: SiteLanguages = _ENGLISH_ONLY,
    post_slugs: dict[str, list[str]] | None = None,
    page_slugs: dict[str, list[str]] | None = None,
    sitemap_endpoints: set[str] | None = None,
) -> Flask:
    """Build a minimal Flask app with the SEO blueprint and optional extra blueprints."""
    config = {
        "SEO_PREFIX": "/prefix",
        "BLOG_PREFIX": "/blog",
        "SITEMAP_EXCLUDED_PREFIXES": sitemap_excluded_prefixes or [],
    }
    config_mock = MagicMock()
    config_mock.__getitem__.side_effect = config.__getitem__
    config_mock.get.side_effect = config.get

    def contents_in(slugs_by_language: dict[str, list[str]], lang: str) -> list[MagicMock]:
        return [MagicMock(slug=slug, date=None) for slug in slugs_by_language.get(lang, [])]

    db_mock = MagicMock()
    db_mock.get_all_posts.side_effect = partial(contents_in, post_slugs or {})
    db_mock.get_all_pages.side_effect = partial(contents_in, page_slugs or {})

    seo_blueprint = seo.create_seo_blueprint(
        db_mock, config_mock, languages, sitemap_endpoints or set()
    )
    app = _make_test_flask_app()
    for bp in extra_blueprints or []:
        app.register_blueprint(bp)
    app.register_blueprint(seo_blueprint)
    return app


def test_robots_txt():
    db_mock = MagicMock()
    config_mock = MagicMock()
    config_mock.__getitem__.return_value = "/prefix"

    seo_blueprint = seo.create_seo_blueprint(db_mock, config_mock, _ENGLISH_ONLY, set())
    app = _make_test_flask_app()
    app.config.update({"DEBUG": True})
    app.register_blueprint(seo_blueprint)

    response = app.test_client().get("/prefix/robots.txt")
    assert response.status_code == 200
    assert "Sitemap: https://localhost/sitemap.xml" in response.text


def test_sitemap_includes_blog_posts():
    config = {
        "SEO_PREFIX": "/prefix",
        "BLOG_PREFIX": "/blog",
        "SITEMAP_EXCLUDED_PREFIXES": [],
    }
    config_mock = MagicMock()
    config_mock.__getitem__.side_effect = config.__getitem__
    config_mock.get.side_effect = config.get

    db_mock = MagicMock()
    db_mock.get_all_pages.return_value = []
    db_mock.get_all_posts.return_value = [
        Post(
            title="title",
            language="en",
            slug="slug",
            tags=["tag/1"],
            contentInMarkdown="content",
            date="2021-02-19",  # type: ignore[arg-type]  # Testing backward compatibility with string dates
            author="author",
            excerpt="excerpt",
            coverImage=Image(
                alternateText="text which is alternative",
                url="https://media.graphcms.com/XvmCDUjYTIq4c9wOIseo",
            ),
            comments=[
                Comment(
                    date="2021-02-19T00:00:00",  # type: ignore[arg-type]  # Testing backward compatibility
                    comment="komentarz",
                    author="autor",
                )
            ],
        )
    ]

    seo_blueprint = seo.create_seo_blueprint(db_mock, config_mock, _ENGLISH_ONLY, set())
    app = _make_test_flask_app()
    app.register_blueprint(seo_blueprint)

    response = app.test_client().get("/prefix/sitemap.xml")
    assert response.status_code == 200
    assert "http://localhost/blog/slug" in response.text


def test_sitemap_lists_posts_of_every_language_served_on_the_host():
    app = _make_seo_app(
        languages=_ENGLISH_AND_UKRAINIAN,
        post_slugs={"en": ["en-slug"], "uk": ["uk-slug"]},
    )
    response = app.test_client().get("/prefix/sitemap.xml")
    assert "http://localhost/blog/en-slug" in response.text
    assert "http://localhost/uk/blog/uk-slug" in response.text


def test_sitemap_lists_pages_of_every_language_served_on_the_host():
    app = _make_seo_app(
        languages=_ENGLISH_AND_UKRAINIAN,
        page_slugs={"en": ["about-tolkien"], "uk": ["pro-tolkina"]},
    )
    response = app.test_client().get("/prefix/sitemap.xml")
    assert "http://localhost/blog/page/about-tolkien" in response.text
    assert "http://localhost/uk/blog/page/pro-tolkina" in response.text


class TestSitemapRoutes:
    def test_lists_route_registered_for_the_sitemap(self) -> None:
        public_bp = Blueprint("public", __name__)

        @public_bp.route("/about", methods=["GET"])
        def about() -> str:
            return "about"

        app = _make_seo_app([public_bp], sitemap_endpoints={"public.about"})
        response = app.test_client().get("/prefix/sitemap.xml")
        assert "http://localhost/about" in response.text

    def test_leaves_out_route_not_registered_for_the_sitemap(self) -> None:
        public_bp = Blueprint("public", __name__)

        @public_bp.route("/about", methods=["GET"])
        def about() -> str:
            return "about"

        app = _make_seo_app([public_bp])
        response = app.test_client().get("/prefix/sitemap.xml")
        assert "/about" not in response.text

    def test_lists_localized_route_for_each_domainless_language_served(self) -> None:
        public_bp = Blueprint("public", __name__)

        @public_bp.route("/about", methods=["GET"])
        @public_bp.route("/<any('uk'):lang_code>/about", methods=["GET"])
        def about(lang_code: str | None = None) -> str:
            return lang_code or "about"

        main_host = _make_seo_app(
            [public_bp], languages=_ENGLISH_AND_UKRAINIAN, sitemap_endpoints={"public.about"}
        )
        response = main_host.test_client().get("/prefix/sitemap.xml")
        assert "http://localhost/about" in response.text
        assert "http://localhost/uk/about" in response.text

        # The test client's host is localhost, so here it is German's own domain.
        german_domain = SiteLanguages(
            domains={"en": "example.com", "uk": None, "de": "localhost"}, default="en"
        )
        domain_host = _make_seo_app(
            [public_bp], languages=german_domain, sitemap_endpoints={"public.about"}
        )
        response = domain_host.test_client().get("/prefix/sitemap.xml")
        assert "http://localhost/about" in response.text
        assert "/uk/about" not in response.text

    def test_leaves_out_registered_route_under_an_excluded_prefix(self) -> None:
        private_bp = Blueprint("private", __name__)

        @private_bp.route("/private/data", methods=["GET"])
        def data() -> str:
            return "secret"

        app = _make_seo_app(
            [private_bp],
            sitemap_excluded_prefixes=["/private/"],
            sitemap_endpoints={"private.data"},
        )
        response = app.test_client().get("/prefix/sitemap.xml")
        assert "/private/data" not in response.text
