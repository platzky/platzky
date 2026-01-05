import typing as t
import urllib.parse

from flask import redirect, render_template, request, session
from flask_minify import Minify
from flask_wtf import CSRFProtect
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from platzky.admin import admin
from platzky.blog import blog
from platzky.config import (
    Config,
    languages_dict,
)
from platzky.db.db import DB
from platzky.db.db_loader import get_db
from platzky.engine import Engine
from platzky.plugin.plugin_loader import plugify
from platzky.seo import seo
from platzky.www_handler import redirect_nonwww_to_www, redirect_www_to_nonwww

_MISSING_OTEL_MSG = (
    "OpenTelemetry is not installed. Install with: "
    "poetry add opentelemetry-api opentelemetry-sdk "
    "opentelemetry-instrumentation-flask opentelemetry-exporter-otlp-proto-grpc"
)


def _url_encode(x: str) -> str:
    """URL-encode a string for safe use in URLs.

    Args:
        x: String to encode

    Returns:
        URL-encoded string with all characters except safe ones escaped
    """
    return urllib.parse.quote(x, safe="")


def _get_language_domain(config: Config, lang: str) -> t.Optional[str]:
    """Get the domain associated with a language.

    Args:
        config: Application configuration
        lang: Language code to look up

    Returns:
        Domain string if language has a dedicated domain, None otherwise
    """
    lang_cfg = config.languages.get(lang)
    if lang_cfg is None:
        return None
    return lang_cfg.domain


def _get_safe_redirect_url(referrer: t.Optional[str], current_host: str) -> str:
    """Get a safe redirect URL by validating the referrer.

    Prevents open redirect vulnerabilities by only allowing same-host redirects.

    Args:
        referrer: The HTTP referrer header value
        current_host: The current request host

    Returns:
        The referrer URL if safe, otherwise "/"
    """
    if not referrer:
        return "/"

    referrer_parsed = urllib.parse.urlparse(referrer)
    # Only redirect to referrer if it's from the same host
    if referrer_parsed.netloc == current_host:
        return referrer
    return "/"


def create_engine(config: Config, db: DB) -> Engine:
    """Create and configure a Platzky Engine instance.

    Sets up the core application with database connection, request handlers,
    route definitions, and context processors for template rendering.

    Args:
        config: Application configuration object
        db: Database instance for data persistence

    Returns:
        Configured Engine instance with plugins loaded
    """
    app = Engine(config, db, __name__)

    @app.before_request
    def handle_www_redirection() -> t.Optional[Response]:
        """Handle WWW subdomain redirection based on configuration.

        Redirects requests to/from www subdomain based on config.use_www setting.

        Returns:
            Redirect response if redirection is needed, None otherwise
        """
        if config.use_www:
            return redirect_nonwww_to_www()
        return redirect_www_to_nonwww()

    @app.route("/lang/<string:lang>", methods=["GET"])
    def change_language(lang: str) -> Response | tuple[str, int]:
        """Change the user's language preference.

        If the language has a dedicated domain, redirects to that domain.
        Otherwise, sets the language in the session and returns to the referrer.

        Args:
            lang: Language code to switch to

        Returns:
            Redirect response to the language domain or referrer page, or 404 if invalid
        """
        # Only allow configured languages
        if lang not in config.languages:
            return render_template("404.html", title="404"), 404

        if new_domain := _get_language_domain(config, lang):
            return redirect(f"{request.scheme}://{new_domain}", code=301)

        session["language"] = lang
        redirect_url = _get_safe_redirect_url(request.referrer, request.host)
        return redirect(redirect_url)

    def url_link(x: str) -> str:
        """URL-encode a string for safe use in URLs.

        Args:
            x: String to encode

        Returns:
            URL-encoded string with all characters except safe ones escaped
        """
        return _url_encode(x)

    @app.context_processor
    def utils() -> dict[str, t.Any]:
        """Provide utility variables and functions to all templates.

        Returns:
            Dictionary of template context variables including app metadata,
            language settings, styling configuration, and helper functions
        """
        locale = app.get_locale()
        lang = config.languages.get(locale)
        flag = lang.flag if lang is not None else ""
        country = lang.country if lang is not None else ""
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
    def dynamic_body() -> dict[str, str]:
        """Provide dynamic body content to all templates.

        Returns:
            Dictionary with dynamic_body content for injection into page body
        """
        return {"dynamic_body": app.dynamic_body}

    @app.context_processor
    def dynamic_head() -> dict[str, str]:
        """Provide dynamic head content to all templates.

        Returns:
            Dictionary with dynamic_head content for injection into page head
        """
        return {"dynamic_head": app.dynamic_head}

    @app.errorhandler(404)
    def page_not_found(_e: HTTPException) -> tuple[str, int]:
        """Handle 404 Not Found errors.

        Args:
            _e: HTTPException object containing error details (unused)

        Returns:
            Tuple of rendered 404 template and HTTP 404 status code
        """
        return render_template("404.html", title="404"), 404

    return plugify(app)


def create_app_from_config(config: Config) -> Engine:
    """Create a fully configured Platzky application from a Config object.

    Initializes the database, creates the engine, sets up telemetry (if enabled),
    registers blueprints (admin, blog, SEO), and configures minification and CSRF
    protection.

    Args:
        config: Application configuration object

    Returns:
        Fully configured Engine instance ready to serve requests

    Raises:
        ImportError: If telemetry is enabled but OpenTelemetry packages are not installed
        ValueError: If telemetry configuration is invalid
    """
    db = get_db(config.db)
    engine = create_engine(config, db)

    # Setup telemetry (optional feature)
    if config.telemetry.enabled:
        try:
            from platzky.telemetry import setup_telemetry

            setup_telemetry(engine, config.telemetry)
        except ImportError as e:
            raise ImportError(_MISSING_OTEL_MSG) from e
        except ValueError as e:
            raise ValueError(
                f"Telemetry configuration error: {e}. "
                "Check your telemetry settings in the configuration file."
            ) from e

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
    """Create a Platzky application from a YAML configuration file.

    Convenience function that loads configuration from a YAML file and
    creates the application.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Fully configured Engine instance ready to serve requests

    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        yaml.YAMLError: If the configuration file contains invalid YAML
        ValidationError: If the configuration doesn't match the expected schema
    """
    config = Config.parse_yaml(config_path)
    return create_app_from_config(config)
