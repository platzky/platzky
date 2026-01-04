import logging
from os.path import dirname
from typing import Any, Callable

from flask import Blueprint, abort, make_response, render_template, request
from markupsafe import Markup
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from . import comment_form

logger = logging.getLogger(__name__)


def create_blog_blueprint(db, blog_prefix: str, locale_func):
    url_prefix = blog_prefix
    blog = Blueprint(
        "blog",
        __name__,
        url_prefix=url_prefix,
        template_folder=f"{dirname(__file__)}/../templates",
    )

    @blog.app_template_filter()
    def markdown(text):
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
        lang = locale_func()
        posts = db.get_all_posts(lang)
        if not posts:
            abort(404)
        posts_sorted = sorted(posts, reverse=True)
        return render_template("blog.html", posts=posts_sorted)

    @blog.route("/feed", methods=["GET"])
    def get_feed() -> Response:
        lang = locale_func()
        response = make_response(render_template("feed.xml", posts=db.get_all_posts(lang)))
        response.headers["Content-Type"] = "application/xml"
        return response

    @blog.route("/<post_slug>", methods=["POST"])
    def post_comment(post_slug: str) -> str:
        comment = request.form.to_dict()
        db.add_comment(
            post_slug=post_slug,
            author_name=comment["author_name"],
            comment=comment["comment"],
        )
        return get_post(post_slug=post_slug)

    def _get_content_or_404(
        getter_func: Callable[[str], Any],
        slug: str,
        *exception_types: type[BaseException],
    ) -> Any:
        """Helper to fetch content from database or abort with 404.

        Args:
            getter_func: Database getter function (e.g., db.get_post, db.get_page)
            slug: Content slug to fetch
            *exception_types: Exception types that indicate content not found

        Returns:
            The fetched content object

        Raises:
            HTTPException: 404 if content not found
        """
        try:
            return getter_func(slug)
        except exception_types as e:
            # IMPROVEMENT: Log the error for debugging
            logger.debug("Content not found for slug '%s': %s", slug, e)
            abort(404)

    @blog.route("/<post_slug>", methods=["GET"])
    def get_post(post_slug: str) -> str:
        post = _get_content_or_404(db.get_post, post_slug, ValueError)
        return render_template(
            "post.html",
            post=post,
            post_slug=post_slug,
            form=comment_form.CommentForm(),
            comment_sent=request.args.get("comment_sent"),
        )

    @blog.route("/page/<path:page_slug>", methods=["GET"])
    def get_page(page_slug: str) -> str:
        # FIX: db.get_page() now raises ValueError instead of StopIteration
        page = _get_content_or_404(db.get_page, page_slug, ValueError)
        cover_image_url = page.coverImage.url if page.coverImage.url else None
        return render_template("page.html", page=page, cover_image=cover_image_url)

    @blog.route("/tag/<path:tag>", methods=["GET"])
    def get_posts_from_tag(tag: str) -> str:
        lang = locale_func()
        posts = db.get_posts_by_tag(tag, lang)
        return render_template("blog.html", posts=posts, subtitle=f" - tag: {tag}")

    return blog
