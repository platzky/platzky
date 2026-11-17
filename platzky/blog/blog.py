"""Blueprint for blog functionality including posts, pages, and comments."""

import logging
import re
from collections.abc import Callable
from email.utils import format_datetime
from os.path import dirname

from flask import Blueprint, abort, make_response, render_template, request
from werkzeug.wrappers import Response

from platzky.content_types import PAGE, POST, ContentSource
from platzky.content_types import ContentType as FilterContentType
from platzky.db.blog_repository import BlogRepository
from platzky.db.exceptions import ReadOnlyStorageError
from platzky.models import LanguageCode, Page, Post
from platzky.shortcodes import ShortcodeError
from platzky.sitemap import SitemapEntry, UrlFor
from platzky.text_format import MARKDOWN

from . import comment_form

logger = logging.getLogger(__name__)


def _abort_unless_in_language(content: Post | Page, language: LanguageCode) -> None:
    """Abort with 404 if content is in another language.

    Args:
        content: The post or page requested
        language: The language of the request

    Raises:
        HTTPException: 404 if the content is in another language
    """
    if content.language != language:
        abort(404)


def create_blog_blueprint(
    blog_repository: BlogRepository,
    blog_prefix: str,
    locale_func: Callable[[], LanguageCode],
    content_transformer: Callable[[ContentSource | str, FilterContentType], str],
) -> Blueprint:
    """Create and configure the blog blueprint with all routes and handlers.

    Args:
        blog_repository: Repository of the posts, pages and index meta to serve
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

    @blog.errorhandler(ShortcodeError)
    def content_error(e: ShortcodeError) -> tuple[str, int]:
        """Show that a post or page cannot be rendered, and log why for whoever can fix it.

        Args:
            e: What in the content's shortcodes is wrong

        Returns:
            Tuple of rendered error template and HTTP 500 status code
        """
        logger.error("Content at %s cannot be rendered: %s", request.path, e)
        return render_template("content_error.html"), 500

    def post_entries(lang: LanguageCode, url: UrlFor) -> list[SitemapEntry]:
        """List every post in a language for the sitemap, dated when it has a date."""
        return [
            SitemapEntry(url(post_slug=post.slug), post.date)
            for post in blog_repository.posts.get_all(lang)
        ]

    def page_entries(lang: LanguageCode, url: UrlFor) -> list[SitemapEntry]:
        """List every page in a language for the sitemap, dated when it has a date."""
        return [
            SitemapEntry(url(page_slug=page.slug), page.date)
            for page in blog_repository.pages.get_all(lang)
        ]

    def index_entries(lang: LanguageCode, url: UrlFor) -> list[SitemapEntry]:
        """List the blog index for the sitemap in a language with posts, which it 404s without."""
        return [SitemapEntry(url())] if blog_repository.posts.get_all(lang) else []

    @blog.route("/", methods=["GET"], multilang=True, sitemap_provider=index_entries)
    def all_posts() -> str:
        """Display all blog posts for the current language.

        Returns:
            Rendered HTML template with all blog posts
        """
        lang = locale_func()
        posts = blog_repository.posts.get_all(lang)
        if not posts:
            abort(404)
        posts_sorted = sorted(posts, reverse=True)
        return render_template(
            "blog.html",
            posts=posts_sorted,
            blog_meta=blog_repository.get_meta(lang),
        )

    @blog.route("/feed", methods=["GET"], multilang=True)
    def get_feed() -> Response:
        """Generate RSS/Atom feed for blog posts.

        Returns:
            XML response containing the RSS/Atom feed
        """
        lang = locale_func()
        response = make_response(
            render_template(
                "feed.xml",
                posts=blog_repository.posts.get_all(lang),
                blog_meta=blog_repository.get_meta(lang),
                rfc822=format_datetime,
            )
        )
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
            HTTPException: 404 if the post is not in the request's language;
                403 if the database backend does not accept writes
        """
        _abort_unless_in_language(blog_repository.posts.get(post_slug), locale_func())
        comment = request.form.to_dict()
        try:
            blog_repository.posts.add_comment(
                post_slug=post_slug,
                author_name=comment["author_name"],
                comment=comment["comment"],
            )
        except ReadOnlyStorageError as e:
            safe_slug = re.sub(r"[\r\n]", "", post_slug)
            logger.warning("Comment rejected for post '%s': %s", safe_slug, e)
            abort(403)
        return get_post(post_slug=post_slug)

    @blog.route("/<post_slug>", methods=["GET"], multilang=True, sitemap_provider=post_entries)
    def get_post(post_slug: str) -> str:
        """Display a single blog post with comments.

        Args:
            post_slug: URL slug of the blog post

        Returns:
            Rendered HTML template of the blog post
        """
        post = blog_repository.posts.get(post_slug)
        _abort_unless_in_language(post, locale_func())
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
        page = blog_repository.pages.get(page_slug)
        _abort_unless_in_language(page, locale_func())
        cover_image_url = (page.coverImage.url or None) if page.coverImage else None
        return render_template(
            "page.html",
            title=page.title,
            excerpt=page.excerpt,
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
        posts = blog_repository.posts.get_by_tag(tag, lang)
        return render_template(
            "blog.html",
            posts=posts,
            subtitle=f" - tag: {tag}",
            blog_meta=blog_repository.get_meta(lang),
        )

    return blog
