from unittest.mock import MagicMock

from flask import Blueprint, Flask

from platzky.models import Comment, Image, Post
from platzky.seo import seo


def _make_seo_app(extra_blueprints: list[Blueprint] | None = None) -> Flask:
    """Build a minimal Flask app with the SEO blueprint and optional extra blueprints."""
    config = {
        "SEO_PREFIX": "/prefix",
        "BLOG_PREFIX": "/blog",
        "SITEMAP_EXCLUDED_PREFIXES": [],
    }
    config_mock = MagicMock()
    config_mock.__getitem__.side_effect = config.__getitem__
    config_mock.get.side_effect = config.get

    db_mock = MagicMock()
    db_mock.get_all_posts.return_value = []

    seo_blueprint = seo.create_seo_blueprint(db_mock, config_mock, lambda: "en")
    app = Flask(__name__)
    app.config.update({"WTF_CSRF_ENABLED": False})
    for bp in extra_blueprints or []:
        app.register_blueprint(bp)
    app.register_blueprint(seo_blueprint)
    return app


def test_robots_txt():
    db_mock = MagicMock()
    config_mock = MagicMock()
    config_mock.__getitem__.return_value = "/prefix"

    seo_blueprint = seo.create_seo_blueprint(db_mock, config_mock, lambda: "en")
    app = Flask(__name__)
    app.config.update({"TESTING": True, "DEBUG": True, "WTF_CSRF_ENABLED": False})
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

    seo_blueprint = seo.create_seo_blueprint(db_mock, config_mock, lambda: "en")
    app = Flask(__name__)
    app.config.update({"WTF_CSRF_ENABLED": False})
    app.register_blueprint(seo_blueprint)

    response = app.test_client().get("/prefix/sitemap.xml")
    assert response.status_code == 200
    assert "http://localhost/blog/slug" in response.text


class TestSitemapFiltering:
    def test_includes_public_get_route(self) -> None:
        public_bp = Blueprint("public", __name__)

        @public_bp.route("/about")
        def about() -> str:
            return "about"

        app = _make_seo_app([public_bp])
        response = app.test_client().get("/prefix/sitemap.xml")
        assert "/about" in response.text

    def test_excludes_post_only_route(self) -> None:
        form_bp = Blueprint("forms", __name__)

        @form_bp.route("/submit", methods=["POST"])
        def submit() -> str:
            return "ok"

        app = _make_seo_app([form_bp])
        response = app.test_client().get("/prefix/sitemap.xml")
        assert "/submit" not in response.text

    def test_excludes_route_with_url_arguments(self) -> None:
        items_bp = Blueprint("items", __name__)

        @items_bp.route("/item/<int:item_id>")
        def item(item_id: int) -> str:
            return str(item_id)

        app = _make_seo_app([items_bp])
        response = app.test_client().get("/prefix/sitemap.xml")
        assert "/item/" not in response.text

    def test_excludes_admin_blueprint(self) -> None:
        admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

        @admin_bp.route("/dashboard")
        def dashboard() -> str:
            return "admin"

        app = _make_seo_app([admin_bp])
        response = app.test_client().get("/prefix/sitemap.xml")
        assert "/admin/dashboard" not in response.text

    def test_excludes_api_blueprint(self) -> None:
        api_bp = Blueprint("api", __name__, url_prefix="/api")

        @api_bp.route("/locations")
        def locations() -> str:
            return "[]"

        app = _make_seo_app([api_bp])
        response = app.test_client().get("/prefix/sitemap.xml")
        assert "/api/locations" not in response.text

    def test_excludes_health_blueprint(self) -> None:
        health_bp = Blueprint("health", __name__, url_prefix="/health")

        @health_bp.route("/liveness")
        def liveness() -> str:
            return "ok"

        app = _make_seo_app([health_bp])
        response = app.test_client().get("/prefix/sitemap.xml")
        assert "/health/liveness" not in response.text

    def test_excludes_lang_prefix(self) -> None:
        lang_bp = Blueprint("lang", __name__)

        @lang_bp.route("/lang/pl")
        def lang_pl() -> str:
            return "ok"

        app = _make_seo_app([lang_bp])
        response = app.test_client().get("/prefix/sitemap.xml")
        assert "/lang/pl" not in response.text

    def test_excludes_custom_prefix_from_config(self) -> None:
        config = {
            "SEO_PREFIX": "/prefix",
            "BLOG_PREFIX": "/blog",
            "SITEMAP_EXCLUDED_PREFIXES": ["/private/"],
        }
        config_mock = MagicMock()
        config_mock.__getitem__.side_effect = config.__getitem__
        config_mock.get.side_effect = config.get

        db_mock = MagicMock()
        db_mock.get_all_posts.return_value = []

        private_bp = Blueprint("private", __name__)

        @private_bp.route("/private/data")
        def data() -> str:
            return "secret"

        seo_blueprint = seo.create_seo_blueprint(db_mock, config_mock, lambda: "en")
        app = Flask(__name__)
        app.config.update({"WTF_CSRF_ENABLED": False})
        app.register_blueprint(private_bp)
        app.register_blueprint(seo_blueprint)

        response = app.test_client().get("/prefix/sitemap.xml")
        assert "/private/data" not in response.text
