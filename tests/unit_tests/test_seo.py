from unittest.mock import MagicMock

from flask import Flask

from platzky.models import Comment, Image, Post
from platzky.seo import seo
from platzky.seo.seo import _INTERNAL_BLUEPRINTS, _INTERNAL_PATH_PREFIXES, _is_public_route


def _make_rule(endpoint, methods, path, arguments=None):
    rule = MagicMock()
    rule.endpoint = endpoint
    rule.methods = methods
    rule.arguments = arguments or set()
    rule.__str__ = lambda self: path
    return rule


def test_config_creation_with_incorrect_mappings():
    db_mock = MagicMock()
    config_mock = MagicMock()
    config_mock.__getitem__.return_value = "/prefix"

    seo_blueprint = seo.create_seo_blueprint(db_mock, config_mock, lambda: "en")
    app = Flask(__name__)
    app.config.update({"TESTING": True, "DEBUG": True, "WTF_CSRF_ENABLED": False})
    app.register_blueprint(seo_blueprint)

    response = app.test_client().get("/prefix/robots.txt")
    assert "Sitemap: https://localhost/sitemap.xml" in response.text
    assert response.status_code == 200


def test_sitemap():
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
    config = {
        "SEO_PREFIX": "/prefix",
        "BLOG_PREFIX": "/blog",
        "DOMAIN_TO_LANG": {"localhost": "en"},
        "SITEMAP_EXCLUDED_PREFIXES": [],
    }
    config_mock = MagicMock()
    config_mock.__getitem__.side_effect = config.__getitem__
    config_mock.get.side_effect = config.get

    seo_blueprint = seo.create_seo_blueprint(db_mock, config_mock, lambda: "en")
    app = Flask(__name__)
    app.config.update({"WTF_CSRF_ENABLED": False})
    app.register_blueprint(seo_blueprint)

    response = app.test_client().get("/prefix/sitemap.xml")
    assert response.status_code == 200
    assert "http://localhost/blog/slug" in response.text


class TestIsPublicRoute:
    def test_accepts_plain_get_route(self):
        rule = _make_rule("main.index", {"GET", "HEAD"}, "/")
        assert _is_public_route(rule)

    def test_rejects_non_get(self):
        rule = _make_rule("main.index", {"POST"}, "/submit")
        assert not _is_public_route(rule)

    def test_rejects_route_with_arguments(self):
        rule = _make_rule("blog.get_post", {"GET"}, "/blog/<slug>", arguments={"slug"})
        assert not _is_public_route(rule)

    def test_rejects_internal_blueprints(self):
        for bp in _INTERNAL_BLUEPRINTS:
            rule = _make_rule(f"{bp}.some_view", {"GET"}, f"/{bp}/something")
            assert not _is_public_route(rule), f"expected {bp} to be excluded"

    def test_rejects_lang_prefix(self):
        rule = _make_rule("change_language", {"GET"}, "/lang/pl")
        assert not _is_public_route(rule)

    def test_rejects_extra_excluded_prefix(self):
        rule = _make_rule("custom.view", {"GET"}, "/private/data")
        assert not _is_public_route(rule, extra_excluded_prefixes=("/private/",))

    def test_accepts_blog_route(self):
        rule = _make_rule("blog.get_page", {"GET"}, "/blog/page/about-us")
        assert _is_public_route(rule)
