"""Blueprint for blog functionality including posts, pages, and comments."""

import logging
import re
from collections.abc import Callable
from os.path import dirname
from typing import TypeVar

from flask import Blueprint, abort, make_response, render_template, request
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from platzky.content_types import PAGE, POST, ContentSource
from platzky.content_types import ContentType as FilterContentType
from platzky.db.db import DB
from platzky.db.exceptions import NotFoundError, ReadOnlyStorageError
from platzky.html_sanitizer import ContentNotAllowed
from platzky.models import Page, Post
from platzky.shortcodes import ShortcodeError
from platzky.sitemap import SitemapEntry, UrlFor, single_url
from platzky.text_format import MARKDOWN

from . import comment_form

_ContentT = TypeVar("_ContentT", Post, Page)

logger = logging.getLogger(__name__)


def create_blog_blueprint(
    db: DB,
    blog_prefix: str,
    locale_func: Callable[[], str],
    content_transformer: Callable[[ContentSource | str, FilterContentType], str],
) -> Blueprint:
    """Create and configure the blog blueprint with all routes and handlers.

    Args:
        db: Database instance for accessing blog content
        blog_prefix: URL prefix for blog routes
        locale_func: Function that returns the current locale/language code
        content_transformer: Function applied to post/page content before rendering

    Returns:
        Configured Flask Blueprint for blog functionality
    """
    blog = Blueprint(
        "blog",
        __name__,
        url_prefix=blog_prefix,
        template_folder=f"{dirname(__file__)}/../templates",
    )

    @blog.errorhandler(404)
    def page_not_found(_e: HTTPException) -> tuple[str, int]:
        """Handle 404 Not Found errors in blog routes.

        Args:
            _e: HTTPException object containing error details (unused)

        Returns:
            Tuple of rendered 404 template and HTTP 404 status code
        """
        return render_template("404.html", title="404"), 404

    @blog.errorhandler(ContentNotAllowed)
    @blog.errorhandler(ShortcodeError)
    def content_error(e: ContentNotAllowed | ShortcodeError) -> tuple[str, int]:
        """Show that a post or page cannot be rendered, and log why for whoever can fix it.

        Args:
            e: What in the content's HTML or shortcodes is wrong

        Returns:
            Tuple of rendered error template and HTTP 500 status code
        """
        logger.error("Content at %s cannot be rendered: %s", request.path, e)
        return render_template("content_error.html"), 500

    def post_entries(lang: str, url: UrlFor) -> list[SitemapEntry]:
        """List every post in a language for the sitemap, dated when it has a date."""
        return [
            SitemapEntry(url(post_slug=post.slug), post.date) for post in db.get_all_posts(lang)
        ]

    def page_entries(lang: str, url: UrlFor) -> list[SitemapEntry]:
        """List every page in a language for the sitemap, dated when it has a date."""
        return [
            SitemapEntry(url(page_slug=page.slug), page.date) for page in db.get_all_pages(lang)
        ]

    @blog.route("/", methods=["GET"], multilang=True, sitemap_provider=single_url)
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
        return render_template("blog.html", posts=posts_sorted, blog_meta=db.get_blog_meta(lang))

    @blog.route("/feed", methods=["GET"], multilang=True)
    def get_feed() -> Response:
        """Generate RSS/Atom feed for blog posts.

        Returns:
            XML response containing the RSS/Atom feed
        """
        lang = locale_func()
        response = make_response(render_template("feed.xml", posts=db.get_all_posts(lang)))
        response.headers["Content-Type"] = "application/xml"
        return response

    @blog.route("/<post_slug>", methods=["POST"], multilang=True)
    def post_comment(post_slug: str) -> str:
        """Handle comment submission for a blog post.

        Args:
            post_slug: URL slug of the blog post

        Returns:
            Rendered HTML template of the blog post with new comment

        Raises:
            HTTPException: 403 if the database backend does not accept writes
        """
        comment = request.form.to_dict()
        try:
            db.add_comment(
                post_slug=post_slug,
                author_name=comment["author_name"],
                comment=comment["comment"],
            )
        except ReadOnlyStorageError as e:
            safe_slug = re.sub(r"[\r\n]", "", post_slug)
            logger.warning("Comment rejected for post '%s': %s", safe_slug, e)
            abort(403)
        return get_post(post_slug=post_slug)

    def _get_content_or_404(
        getter_func: Callable[[str], _ContentT],
        slug: str,
    ) -> _ContentT:
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
        except NotFoundError as e:
            logger.debug("Content not found for slug '%s': %s", slug, e)
            abort(404)

    @blog.route("/<post_slug>", methods=["GET"], multilang=True, sitemap_provider=post_entries)
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
            # Vouched for: a post body is written by someone with CMS write access.
            content=content_transformer(ContentSource(post.contentInMarkdown, MARKDOWN), POST),
            post_slug=post_slug,
            form=comment_form.CommentForm(),
            comment_sent=request.args.get("comment_sent"),
        )

    @blog.route(
        "/page/<path:page_slug>", methods=["GET"], multilang=True, sitemap_provider=page_entries
    )
    def get_page(page_slug: str) -> str:
        """Display a static page.

        Args:
            page_slug: URL slug of the page

        Returns:
            Rendered HTML template of the page
        """
        page = _get_content_or_404(db.get_page, page_slug)
        cover_image_url = (page.coverImage.url or None) if page.coverImage else None
        return render_template(
            "page.html",
            title=page.title,
            css=page.css,
            # Vouched for, as a post body is.
            content=content_transformer(ContentSource(page.contentInMarkdown, MARKDOWN), PAGE),
            cover_image=cover_image_url,
        )

    @blog.route("/tag/<path:tag>", methods=["GET"], multilang=True)
    def get_posts_from_tag(tag: str) -> str:
        """Display all blog posts with a specific tag.

        Args:
            tag: Tag name to filter posts by

        Returns:
            Rendered HTML template with filtered blog posts
        """
        lang = locale_func()
        posts = db.get_posts_by_tag(tag, lang)
        return render_template(
            "blog.html", posts=posts, subtitle=f" - tag: {tag}", blog_meta=db.get_blog_meta(lang)
        )

    return blog
