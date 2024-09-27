import typing as t
import urllib.parse
from os.path import dirname

from flask import Blueprint, current_app, make_response, render_template, request


def create_seo_blueprint(db, config: dict[str, t.Any], locale_func: t.Callable[[], str]):
    seo = Blueprint(
        "seo",
        __name__,
        url_prefix=config["SEO_PREFIX"],
        template_folder=f"{dirname(__file__)}/../templates",
    )

    @seo.route("/robots.txt")
    def robots():
        robots_response = render_template("robots.txt", domain=request.host, mimetype="text/plain")
        response = make_response(robots_response)
        response.headers["Content-Type"] = "text/plain"
        return response

    def get_blog_entries(host_base, lang, db, blog_prefix):
        dynamic_urls = list()
        print(blog_prefix)
        for post in db.get_all_posts(
            lang
        ):  # TODO add get_list_of_posts for faster getting just list of it
            slug = post.slug
            datet = post.date.split("T")[0]
            url = {"loc": f"{host_base}{blog_prefix}/{slug}", "lastmod": datet}
            dynamic_urls.append(url)
        return dynamic_urls

    @seo.route("/sitemap.xml")  # TODO try to replace sitemap logic with flask-sitemap module
    def sitemap():
        """
        Route to dynamically generate a sitemap of your website/application.
        lastmod and priority tags omitted on static pages.
        lastmod included on dynamic content such as seo posts.
        """
        lang = locale_func()

        global url
        host_components = urllib.parse.urlparse(request.host_url)
        host_base = host_components.scheme + "://" + host_components.netloc

        # Static routes with static content
        static_urls = list()
        for rule in current_app.url_map.iter_rules():
            if rule.methods is not None and "GET" in rule.methods and len(rule.arguments) == 0:
                url = {"loc": f"{host_base}{rule!s}"}
                static_urls.append(url)

        dynamic_urls = get_blog_entries(host_base, lang, db, config["BLOG_PREFIX"])

        statics = list({v["loc"]: v for v in static_urls}.values())
        dynamics = list({v["loc"]: v for v in dynamic_urls}.values())
        xml_sitemap = render_template(
            "sitemap.xml",
            static_urls=statics,
            dynamic_urls=dynamics,
            host_base=host_base,
        )
        response = make_response(xml_sitemap)
        response.headers["Content-Type"] = "application/xml"
        return response

    return seo


# TODO add tests which would check that sitemap is different for different languages
