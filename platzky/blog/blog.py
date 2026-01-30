"""Blueprint for blog functionality including posts, pages, and comments."""

import logging
from collections.abc import Callable
from os.path import dirname
from typing import TypeVar

from flask import Blueprint, abort, make_response, render_template, request
from markupsafe import Markup
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from platzky.db.db import DB
from platzky.models import Page, Post

from . import comment_form

ContentType = TypeVar("ContentType", Post, Page)

logger = logging.getLogger(__name__)


def create_blog_blueprint(db: DB, blog_prefix: str, locale_func: Callable[[], str]) -> Blueprint:
    """Create and configure the blog blueprint with all routes and handlers.

    Args:
        db: Database instance for accessing blog content
        blog_prefix: URL prefix for blog routes
        locale_func: Function that returns the current locale/language code

    Returns:
        Configured Flask Blueprint for blog functionality
    """
    blog = Blueprint(
        "blog",
        __name__,
        url_prefix=blog_prefix,
        template_folder=f"{dirname(__file__)}/../templates",
    )

    @blog.app_template_filter()
    def markdown(text: str) -> Markup:
        """Template filter to render markdown text as safe HTML.

        Args:
            text: Markdown text to be rendered

        Returns:
            Markup object containing safe HTML
        """
        return Markup(text)

    @blog.errorhandler(404)
    def page_not_found(_e: HTTPException) -> tuple[str, int]:
        """Handle 404 Not Found errors in blog routes.

        Args:
            _e: HTTPException object containing error details (unused)

        Returns:
            Tuple of rendered 404 template and HTTP 404 status code
        """
        return render_template("404.html", title="404"), 404

    @blog.route("/", methods=["GET"])
    def all_posts() -> str:
        """Display all blog posts for the current language.

        Returns:
            Rendered HTML template with all blog posts
        """
        lang = locale_func()
        posts = db.get_all_posts(lang)
        if not posts:
            abort(404)
        posts_sorted = sorted(posts, reverse=True)
        return render_template("blog.html", posts=posts_sorted)

    @blog.route("/feed", methods=["GET"])
    def get_feed() -> Response:
        """Generate RSS/Atom feed for blog posts.

        Returns:
            XML response containing the RSS/Atom feed
        """
        lang = locale_func()
        response = make_response(render_template("feed.xml", posts=db.get_all_posts(lang)))
        response.headers["Content-Type"] = "application/xml"
        return response

    @blog.route("/<post_slug>", methods=["POST"])
    def post_comment(post_slug: str) -> str:
        """Handle comment submission for a blog post.

        Args:
            post_slug: URL slug of the blog post

        Returns:
            Rendered HTML template of the blog post with new comment
        """
        comment = request.form.to_dict()
        db.add_comment(
            post_slug=post_slug,
            author_name=comment["author_name"],
            comment=comment["comment"],
        )
        return get_post(post_slug=post_slug)

    def _get_content_or_404(
        getter_func: Callable[[str], ContentType],
        slug: str,
    ) -> ContentType:
        """Helper to fetch content from database or abort with 404.

        Args:
            getter_func: Database getter function (e.g., db.get_post, db.get_page)
            slug: Content slug to fetch

        Returns:
            The fetched content object

        Raises:
            HTTPException: 404 if content not found
        """
        try:
            return getter_func(slug)
        except ValueError as e:
            logger.debug("Content not found for slug '%s': %s", slug, e)
            abort(404)

    @blog.route("/<post_slug>", methods=["GET"])
    def get_post(post_slug: str) -> str:
        """Display a single blog post with comments.

        Args:
            post_slug: URL slug of the blog post

        Returns:
            Rendered HTML template of the blog post
        """
        post = _get_content_or_404(db.get_post, post_slug)
        return render_template(
            "post.html",
            post=post,
            post_slug=post_slug,
            form=comment_form.CommentForm(),
            comment_sent=request.args.get("comment_sent"),
        )

    @blog.route("/page/<path:page_slug>", methods=["GET"])
    def get_page(page_slug: str) -> str:
        """Display a static page.

        Args:
            page_slug: URL slug of the page

        Returns:
            Rendered HTML template of the page
        """
        page = _get_content_or_404(db.get_page, page_slug)
        return render_template("page.html", page=page, cover_image=page.coverImage.url or None)

    @blog.route("/tag/<path:tag>", methods=["GET"])
    def get_posts_from_tag(tag: str) -> str:
        """Display all blog posts with a specific tag.

        Args:
            tag: Tag name to filter posts by

        Returns:
            Rendered HTML template with filtered blog posts
        """
        lang = locale_func()
        posts = db.get_posts_by_tag(tag, lang)
        return render_template("blog.html", posts=posts, subtitle=f" - tag: {tag}")

    return blog
