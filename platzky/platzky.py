import typing as t
import urllib.parse

from flask import redirect, render_template, request, session
from flask_minify import Minify
from flask_wtf import CSRFProtect

from platzky.admin import admin
from platzky.blog import blog
from platzky.config import (
    Config,
    languages_dict,
)
from platzky.db.db_loader import get_db
from platzky.engine import Engine
from platzky.plugin.plugin_loader import plugify
from platzky.seo import seo
from platzky.www_handler import redirect_nonwww_to_www, redirect_www_to_nonwww


def create_engine(config: Config, db) -> Engine:
    app = Engine(config, db, __name__)

    @app.before_request
    def handle_www_redirection():
        if config.use_www:
            return redirect_nonwww_to_www()
        else:
            return redirect_www_to_nonwww()

    def get_langs_domain(lang: str) -> t.Optional[str]:
        lang_cfg = config.languages.get(lang)
        if lang_cfg is None:
            return None
        return lang_cfg.domain

    @app.route("/lang/<string:lang>", methods=["GET"])
    def change_language(lang):
        if new_domain := get_langs_domain(lang):
            return redirect("http://" + new_domain, code=301)
        else:
            session["language"] = lang
            return redirect(request.referrer)

    def url_link(x: str) -> str:
        return urllib.parse.quote(x, safe="")

    @app.context_processor
    def utils():
        locale = app.get_locale()
        flag = lang.flag if (lang := config.languages.get(locale)) is not None else ""
        country = lang.country if (lang := config.languages.get(locale)) is not None else ""
        return {
            "app_name": config.app_name,
            "app_description": app.db.get_app_description(locale) or config.app_name,
            "languages": languages_dict(config.languages),
            "current_flag": flag,
            "current_lang_country": country,
            "current_language": locale,
            "url_link": url_link,
            "menu_items": app.db.get_menu_items_in_lang(locale),
            "logo_url": app.db.get_logo_url(),
            "favicon_url": app.db.get_favicon_url(),
            "font": app.db.get_font(),
            "primary_color": app.db.get_primary_color(),
            "secondary_color": app.db.get_secondary_color(),
        }

    @app.context_processor
    def dynamic_body():
        return {"dynamic_body": app.dynamic_body}

    @app.context_processor
    def dynamic_head():
        return {"dynamic_head": app.dynamic_head}

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html", title="404"), 404

    return plugify(app)


def create_app_from_config(config: Config) -> Engine:
    db = get_db(config.db)
    engine = create_engine(config, db)

    # Setup telemetry
    from platzky.telemetry import setup_telemetry

    setup_telemetry(engine, config.telemetry)

    admin_blueprint = admin.create_admin_blueprint(
        login_methods=engine.login_methods, cms_modules=engine.cms_modules
    )

    if config.feature_flags and config.feature_flags.get("FAKE_LOGIN", False):
        from platzky.admin.fake_login import get_fake_login_html, setup_fake_login_routes

        engine.login_methods.append(get_fake_login_html())
        admin_blueprint = setup_fake_login_routes(admin_blueprint)

    blog_blueprint = blog.create_blog_blueprint(
        db=engine.db,
        blog_prefix=config.blog_prefix,
        locale_func=engine.get_locale,
    )
    seo_blueprint = seo.create_seo_blueprint(
        db=engine.db, config=engine.config, locale_func=engine.get_locale
    )
    engine.register_blueprint(admin_blueprint)
    engine.register_blueprint(blog_blueprint)
    engine.register_blueprint(seo_blueprint)

    Minify(app=engine, html=True, js=True, cssless=True)
    CSRFProtect(app=engine)
    return engine


def create_app(config_path: str) -> Engine:
    config = Config.parse_yaml(config_path)
    return create_app_from_config(config)
