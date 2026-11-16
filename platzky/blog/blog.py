"""Blueprint for blog functionality including posts, pages, and comments."""

import logging
import re
from collections.abc import Callable
from os.path import dirname
from typing import TypeVar

from flask import Blueprint, abort, make_response, redirect, render_template, request
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from platzky.content_types import PAGE, POST, ContentSource
from platzky.content_types import ContentType as FilterContentType
from platzky.db.blog_repository import BlogRepository
from platzky.db.exceptions import NotFoundError, ReadOnlyStorageError
from platzky.models import LanguageCode, Page, Post
from platzky.shortcodes import ShortcodeError
from platzky.sitemap import SitemapEntry, UrlFor, single_url
from platzky.text_format import MARKDOWN

from . import comment_form

_ContentT = TypeVar("_ContentT", Post, Page)

logger = logging.getLogger(__name__)


def create_blog_blueprint(
    blog_repository: BlogRepository,
    blog_prefix: str,
    locale_func: Callable[[], LanguageCode],
    content_transformer: Callable[[ContentSource | str, FilterContentType], str],
    url_for_language: Callable[..., str],
) -> Blueprint:
    """Create and configure the blog blueprint with all routes and handlers.

    Args:
        blog_repository: Repository of the posts, pages and index meta to serve
        blog_prefix: URL prefix for blog routes
        locale_func: Function that returns the current locale/language code
        content_transformer: Function applied to post/page content before rendering
        url_for_language: Builds an endpoint's URL in a language, as ``Engine.url_for_language``

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

    @blog.route("/", methods=["GET"], multilang=True, sitemap_provider=single_url)
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
            render_template("feed.xml", posts=blog_repository.posts.get_all(lang))
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
        _get_content(blog_repository.posts.get, post_slug, "blog.get_post")
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

    def _get_content(
        getter_func: Callable[[str], _ContentT],
        slug: str,
        endpoint: str,
    ) -> _ContentT:
        """Fetch the content to show at the request's URL.

        Args:
            getter_func: Database getter function (e.g., a repository's ``get``)
            slug: Content slug to fetch
            endpoint: Endpoint of the content's own URL; requested through another one, such as
                the home page or the comment form, content in another language is not found

        Returns:
            The fetched content object

        Raises:
            HTTPException: 301 to the content's URL in its language; 404 if content is not
                found, its language is not served, or it is requested through another endpoint
        """
        try:
            content = getter_func(slug)
        except NotFoundError as e:
            logger.debug("Content not found for slug '%s': %s", slug, e)
            abort(404)
        if content.language == locale_func():
            return content
        if request.endpoint != endpoint:
            abort(404)
        try:
            url = url_for_language(
                endpoint, content.language, _external=True, **(request.view_args or {})
            )
        except ValueError as e:
            logger.debug(
                "Content '%s' is in %s, which is not served: %s", slug, content.language, e
            )
            abort(404)
        abort(redirect(url, 301))

    @blog.route("/<post_slug>", methods=["GET"], multilang=True, sitemap_provider=post_entries)
    def get_post(post_slug: str) -> str:
        """Display a single blog post with comments.

        Args:
            post_slug: URL slug of the blog post

        Returns:
            Rendered HTML template of the blog post
        """
        post = _get_content(blog_repository.posts.get, post_slug, "blog.get_post")
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
        page = _get_content(blog_repository.pages.get, page_slug, "blog.get_page")
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
        posts = blog_repository.posts.get_by_tag(tag, lang)
        return render_template(
            "blog.html",
            posts=posts,
            subtitle=f" - tag: {tag}",
            blog_meta=blog_repository.get_meta(lang),
        )

    return blog
