import os
import typing as t
import urllib.parse

from flask import Flask, redirect, render_template, request, session
from flask_babel import Babel
from flask_minify import Minify

from platzky.admin import admin
from platzky.blog import blog
from platzky.config import (
    Config,
    languages_dict,
)
from platzky.db.db_loader import get_db
from platzky.plugin_loader import plugify
from platzky.seo import seo
from platzky.www_handler import redirect_nonwww_to_www, redirect_www_to_nonwww


class Engine(Flask):
    def __init__(self, config: Config, db, import_name):
        super().__init__(import_name)
        self.config.from_mapping(config.model_dump(by_alias=True))
        self.db = db
        self.notifiers = []
        self.login_methods = []
        self.dynamic_body = ""
        self.dynamic_head = ""
        directory = os.path.dirname(os.path.realpath(__file__))
        locale_dir = os.path.join(directory, "locale")
        config.translation_directories.append(locale_dir)

        babel_translation_directories = ";".join(config.translation_directories)
        self.babel = Babel(
            self,
            locale_selector=self.get_locale,
            default_translation_directories=babel_translation_directories,
        )

    def notify(self, message: str):
        for notifier in self.notifiers:
            notifier(message)

    def add_notifier(self, notifier):
        self.notifiers.append(notifier)

    def add_login_method(self, login_method):
        self.login_methods.append(login_method)

    def add_dynamic_body(self, body: str):
        self.dynamic_body += body

    def add_dynamic_head(self, body: str):
        self.dynamic_head += body

    def get_locale(self) -> str:
        domain = request.headers["Host"]
        domain_to_lang = self.config.get("DOMAIN_TO_LANG")

        languages = self.config.get("LANGUAGES", {}).keys()
        backup_lang = session.get(
            "language",
            request.accept_languages.best_match(languages, "en"),
        )

        if domain_to_lang:
            lang = domain_to_lang.get(domain, backup_lang)
        else:
            lang = backup_lang

        session["language"] = lang
        return lang


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
    engine = create_engine_from_config(config)
    admin_blueprint = admin.create_admin_blueprint(login_methods=engine.login_methods, db=engine.db, locale_func=engine.get_locale)
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
    return engine


def create_engine_from_config(config: Config) -> Engine:
    """Create an engine from a config."""
    db = get_db(config.db)
    return create_engine(config, db)


def create_app(config_path: str) -> Engine:
    config = Config.parse_yaml(config_path)
    return create_app_from_config(config)
