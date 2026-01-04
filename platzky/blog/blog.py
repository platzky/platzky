from os.path import dirname

from flask import Blueprint, make_response, render_template, request
from markupsafe import Markup
from werkzeug.exceptions import HTTPException

from . import comment_form


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
    def all_posts():
        lang = locale_func()
        posts = db.get_all_posts(lang)
        if not posts:
            return page_not_found("no posts")
        posts_sorted = sorted(posts, reverse=True)
        return render_template("blog.html", posts=posts_sorted)

    @blog.route("/feed", methods=["GET"])
    def get_feed():
        lang = locale_func()
        response = make_response(render_template("feed.xml", posts=db.get_all_posts(lang)))
        response.headers["Content-Type"] = "application/xml"
        return response

    @blog.route("/<post_slug>", methods=["POST"])
    def post_comment(post_slug):
        comment = request.form.to_dict()
        db.add_comment(
            post_slug=post_slug,
            author_name=comment["author_name"],
            comment=comment["comment"],
        )
        return get_post(post_slug=post_slug)

    @blog.route("/<post_slug>", methods=["GET"])
    def get_post(post_slug):
        try:
            post = db.get_post(post_slug)
            return render_template(
                "post.html",
                post=post,
                post_slug=post_slug,
                form=comment_form.CommentForm(),
                comment_sent=request.args.get("comment_sent"),
            )
        except ValueError:
            return page_not_found(f"no post with slug {post_slug}")
        except Exception as e:
            return page_not_found(str(e))

    @blog.route("/page/<path:page_slug>", methods=["GET"])
    def get_page(
        page_slug,
    ):  # TODO refactor to share code with get_post since they are very similar
        try:
            page = db.get_page(page_slug)
            if cover_image := page.coverImage:
                cover_image_url = cover_image.url
            else:
                cover_image_url = None
            return render_template("page.html", page=page, cover_image=cover_image_url)
        except ValueError:
            return page_not_found("no page with slug {page_slug}")
        except Exception as e:
            return page_not_found(str(e))

    @blog.route("/tag/<path:tag>", methods=["GET"])
    def get_posts_from_tag(tag):
        lang = locale_func()
        posts = db.get_posts_by_tag(tag, lang)
        return render_template("blog.html", posts=posts, subtitle=f" - tag: {tag}")

    return blog
