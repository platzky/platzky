"""Application factory — assembles config, database, engine, plugins, and blueprints."""

import logging
import typing as t
import urllib.parse
from collections.abc import Callable, Iterable, Mapping, Sequence

import jinja2.ext
from flask import make_response, redirect, render_template, request
from flask.typing import ResponseReturnValue
from flask_babel import force_locale, gettext
from flask_minify import Minify
from flask_wtf import CSRFProtect
from markupsafe import Markup
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.wrappers import Response

from platzky.admin import admin
from platzky.blog import blog
from platzky.config import (
    Config,
    languages_dict,
)
from platzky.content_types import FOOTER, PAGE, POST, ContentSource, ContentType
from platzky.db.db import DB
from platzky.db.db_loader import get_db
from platzky.db.site_config_repository import SiteSettings
from platzky.engine import Engine
from platzky.feature_flags import FakeLogin
from platzky.home_page import (
    home_page_paths_with_default,
    home_page_target_response,
    resolve_home_page_paths,
    warn_about_languages_without_a_home_page,
)
from platzky.language_routing import (
    any_converter,
)
from platzky.login import login
from platzky.models import LanguageCode
from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.plugin.login import LoginPluginBase
from platzky.plugin.plugin import PluginBase
from platzky.plugin.plugin_loader import plugify
from platzky.seo import seo
from platzky.shortcodes import Shortcode, ShortcodeError
from platzky.shortcodes.builtins import get_builtin_shortcodes
from platzky.sitemap import single_url
from platzky.text_format import MARKDOWN
from platzky.www_handler import redirect_nonwww_to_www, redirect_www_to_nonwww

logger = logging.getLogger(__name__)

_LOG_FORMAT = "%(name)s - %(levelname)s - %(message)s"
_DEFAULT_LOG_LEVEL = "INFO"

_MISSING_OTEL_MSG = (
    "OpenTelemetry is not installed. Install with: "
    "poetry add opentelemetry-api opentelemetry-sdk "
    "opentelemetry-instrumentation-flask opentelemetry-exporter-otlp-proto-grpc"
)

_NOT_FOUND_TEMPLATE = "404.html"

_HSTS_MAX_AGE = 31536000  # one year


def _gather_shortcodes_and_extensions(
    plugins: Iterable[ContentTransformerPluginBase],
    registered_shortcodes: dict[str, Shortcode],
) -> tuple[dict[str, Shortcode], list[type[jinja2.ext.Extension]]]:
    """Collect shortcodes and Jinja2 extensions from a set of content-transformer plugins.

    A tag name already claimed is kept by whoever claimed it first, and the loser is
    logged. Built-ins are registered before any plugin, so a plugin cannot displace
    ``[image]``, ``[link]`` or ``[hero]``, and among plugins the earlier config key wins —
    the same rule prose follows, since transformers run in that order and the first to own
    a tag consumes it.

    Args:
        plugins: Content-transformer plugins to inspect.
        registered_shortcodes: Shortcodes already registered (used for duplicate detection only).

    Returns:
        Tuple of (new shortcodes dict, Jinja2 extension class list).
    """
    shortcodes: dict[str, Shortcode] = {}
    extensions: list[type[jinja2.ext.Extension]] = []
    for plugin in plugins:
        for tag_name, shortcode in plugin.shortcodes.items():
            if tag_name in registered_shortcodes or tag_name in shortcodes:
                logger.warning(
                    "Plugin %r registers shortcode %r, which is already registered. The "
                    "earlier registration wins; reorder the plugins in the config to "
                    "change which.",
                    type(plugin).__name__,
                    tag_name,
                )
                continue
            shortcodes[tag_name] = shortcode
        extensions.extend(plugin.get_jinja_extensions())
    return shortcodes, extensions


_builtin_shortcodes = get_builtin_shortcodes()
_builtin_tag_list = ", ".join(f"[{name}]" for name in _builtin_shortcodes)


class _BuiltinShortcodeTransformer(ContentTransformerPluginBase):
    """Built-in shortcodes, always registered for posts, pages and footers."""

    accepted_content_types: Mapping[ContentType, str] = {
        POST: f"Renders the built-in shortcodes ({_builtin_tag_list}) an author wrote in a post.",
        PAGE: f"Renders the built-in shortcodes ({_builtin_tag_list}) an author wrote in a page.",
        FOOTER: f"Renders the built-in shortcodes ({_builtin_tag_list}) written in a footer.",
    }
    shortcodes = _builtin_shortcodes


def _url_encode(x: str) -> str:
    """URL-encode a string for safe use in URLs.

    Args:
        x: String to encode

    Returns:
        URL-encoded string with all characters except safe ones escaped
    """
    return urllib.parse.quote(x, safe="")


def _rendered_footer(app: Engine, content: str) -> Markup:
    """Render footer markup for a template, or nothing at all if it cannot be rendered.

    Args:
        app: The application, for its content transformers.
        content: The footer as an author wrote it, in Markdown with shortcodes.

    Returns:
        The rendered footer, empty when a shortcode in it is malformed.
    """
    # Only someone with CMS access can write the footer, so its HTML is embedded as
    # written. Passing a plain str instead would escape the author's tags into visible
    # text, and would have the shortcode parser treat their mistakes as a stranger's.
    authored = ContentSource(content, MARKDOWN)
    try:
        rendered = app.transform_content(authored, FOOTER)
    except ShortcodeError:
        # This is called on every page render, so one malformed tag would otherwise 500
        # the whole site, the 404 handler included. Drop the footer instead; the log names
        # the bracket at fault.
        logger.exception("Site-wide footer could not be rendered; showing no footer")
        rendered = Markup("")
    return rendered


def _language_suggestion(config: Config, lang: LanguageCode, url: str) -> dict[str, str]:
    """Return the texts and link of a popup suggesting a language, written in that language.

    Args:
        config: Application configuration.
        lang: Code of the suggested language.
        url: Where the popup's link leads.

    Returns:
        The link ``url``, the ``message``, and the labels of the ``switch`` link and the
        ``close`` button.
    """
    name = config.languages[lang].name
    with force_locale(lang):
        return {
            "url": url,
            "message": gettext("This site is also available in %(language)s.", language=name),
            "switch": gettext("Switch to %(language)s", language=name),
            "close": gettext("Close"),
        }


def _language_suggestions(
    config: Config,
    locale: LanguageCode,
    alternates: Mapping[LanguageCode, str],
    home_url: Callable[[LanguageCode], str],
) -> dict[LanguageCode, dict[str, str]]:
    """Return a popup suggesting each configured language other than the current page's.

    Args:
        config: Application configuration.
        locale: Language of the current page.
        alternates: URLs of the current page in each language, if it has equivalents.
        home_url: URL of a language's home, for a page without an equivalent in it.

    Returns:
        Language codes mapped to their popups.
    """
    return {
        lang: _language_suggestion(
            config,
            lang,
            alternates.get(lang) or home_url(lang),
        )
        for lang in config.languages
        if lang != locale
    }


def _www_redirection_response(config: Config) -> t.Optional[Response]:
    """Handle WWW subdomain redirection based on configuration.

    Args:
        config: Application configuration object

    Returns:
        Redirect response if redirection is needed, None otherwise
    """
    if config.use_www:
        return redirect_nonwww_to_www()
    return redirect_www_to_nonwww()


def _change_language_response(
    config: Config, lang: LanguageCode, home_url: Callable[[LanguageCode], str]
) -> Response:
    """Redirect to the home page of a language.

    Args:
        config: Application configuration object
        lang: Language code to switch to
        home_url: URL of a language's home

    Returns:
        Redirect to the language's home URL, or 404 if the language is not configured
    """
    if lang not in config.languages:
        return make_response(render_template(_NOT_FOUND_TEMPLATE, title="404"), 404)
    return redirect(home_url(lang), code=302)


def create_engine(
    config: Config,
    db: DB,
    extra_plugin_bases: Sequence[type[PluginBase]] = (),
    extra_plugins_entrypoints: Sequence[str] = (),
    extra_content_types: Sequence[ContentType] = (),
) -> Engine:
    """Create and configure a Platzky Engine instance.

    Sets up the core application with database connection, request handlers,
    route definitions, and context processors for template rendering.

    Args:
        config: Application configuration object
        db: Database instance for data persistence
        extra_plugin_bases: App specific registered capability base classes (see ``Engine``).
        extra_plugins_entrypoints: App specific registered entry-point groups (see ``Engine``).
        extra_content_types: App specific content types (see ``Engine``).

    Returns:
        Configured Engine instance with plugins loaded. Its ``home_page_paths`` are not yet
        checked against the routes, which ``create_app_from_config`` does.
    """
    app = Engine(
        config,
        db,
        __name__,
        extra_plugin_bases,
        extra_plugins_entrypoints,
        extra_content_types,
    )

    app.home_page_paths = home_page_paths_with_default(
        {
            language: db.site_config.get_localized_content(language).home_page_path
            for language in config.language_routing.languages
        },
        config.default_language,
        config.blog_prefix,
    )

    @app.before_request
    def handle_www_redirection() -> t.Optional[Response]:
        """Handle WWW subdomain redirection based on configuration.

        Redirects requests to/from www subdomain based on config.use_www setting.

        Returns:
            Redirect response if redirection is needed, None otherwise
        """
        return _www_redirection_response(config)

    def home_url(lang: LanguageCode) -> str:
        """Return the URL of the home page in a language."""
        return app.url_for_language("home_page", lang, _external=True)

    @app.route("/lang/<string:lang>", methods=["GET"])
    def change_language(lang: LanguageCode) -> Response:
        """Redirect to the home page of a language.

        Args:
            lang: Language code to switch to

        Returns:
            Redirect to the language's home URL, or 404 if the language is not configured
        """
        return _change_language_response(config, lang, home_url)

    def domainful_language_prefix(lang: LanguageCode, path: str) -> Response:
        """Redirect a URL prefixed with a language that is served without a prefix.

        Args:
            lang: Code of the default language, or of a language with its own domain
            path: The URL path after the language prefix

        Returns:
            Permanent redirect to the page where that language is served
        """
        return app.localized_redirect(lang, f"/{path}")

    domainful = config.language_routing.domainful_languages
    if domainful:
        prefix = f"/<{any_converter(domainful)}:lang>"
        app.add_url_rule(
            f"{prefix}/",
            view_func=domainful_language_prefix,
            defaults={"path": ""},
            methods=["GET"],
        )
        app.add_url_rule(
            f"{prefix}/<path:path>", view_func=domainful_language_prefix, methods=["GET"]
        )

    @app.route("/", methods=["GET"], multilang=True, sitemap_provider=single_url)
    def home_page() -> ResponseReturnValue:
        """Render the configured homepage.

        A language without a home page of its own redirects (302) to the home of the default
        language, as a page may be added to it later.

        Returns:
            Rendered HTML of the resolved destination, the 404 page, or the redirect.
        """
        target_path = app.home_page_paths.get(app.get_locale())
        if target_path is None:
            return redirect(home_url(config.default_language), code=302)
        return home_page_target_response(
            app.url_map.bind(request.host), app.view_functions, target_path
        )

    @app.context_processor
    def utils() -> dict[str, t.Any]:
        """Provide utility variables and functions to all templates.

        Returns:
            Dictionary of template context variables including app metadata,
            language settings, styling configuration, the menu, the rendered footer
            (empty when none is configured), and helper functions
        """
        locale = app.get_locale()
        lang = config.languages.get(locale)
        flag = lang.flag if lang else ""
        country = lang.country if lang else ""
        alternates = app.current_page_language_alternates()
        localized = app.db.site_config.get_localized_content(locale)
        site_settings = SiteSettings.from_layers(app.db.site_config.get_site_config(), localized)
        app_name = site_settings.app_name or config.app_name
        return {
            "app_name": app_name,
            "app_title": site_settings.app_title or app_name,
            "app_description": site_settings.app_description or app_name,
            "languages": languages_dict(config.languages),
            "current_flag": flag,
            "current_lang_country": country,
            "current_language": locale,
            "default_language": config.default_language,
            "language_alternates": alternates,
            "language_suggestions": _language_suggestions(config, locale, alternates, home_url),
            "url_link": _url_encode,
            "url_for_language": app.url_for_language,
            "menu_items": localized.menu_items,
            "logo_url": site_settings.logo_url,
            "favicon_url": site_settings.favicon_url,
            "font": site_settings.font,
            "primary_color": site_settings.primary_color,
            "secondary_color": site_settings.secondary_color,
            "footer": _rendered_footer(app, localized.footer.content),
            "footer_collapsible": localized.footer.collapsible,
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
        return render_template(_NOT_FOUND_TEMPLATE, title="404"), 404

    return plugify(app)


def _configure_logging(level: str) -> None:
    """Log the whole application at the given level, adding a stderr handler unless one exists.

    Args:
        level: Level name for the root logger, such as DEBUG or INFO
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root_logger.addHandler(handler)


def _add_hsts_header(response: Response) -> Response:
    """Tell browsers to use only HTTPS for this host, on responses served over HTTPS."""
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = f"max-age={_HSTS_MAX_AGE}"
    return response


def _enforce_https(engine: Engine) -> None:
    """Trust the proxy's X-Forwarded-Proto, mark the session cookie secure and send HSTS."""
    # App Engine and Cloud Run terminate TLS in Google's front end, one hop in front of the app.
    engine.wsgi_app = ProxyFix(engine.wsgi_app, x_for=0, x_proto=1)
    engine.config["SESSION_COOKIE_SECURE"] = True
    engine.after_request(_add_hsts_header)


def create_app_from_config(
    config: Config,
    extra_plugin_bases: Sequence[type[PluginBase]] = (),
    extra_plugins_entrypoints: Sequence[str] = (),
    extra_content_types: Sequence[ContentType] = (),
    development: bool = False,
) -> Engine:
    """Create a fully configured Platzky application from a Config object.

    Applies LOG_LEVEL to the root logger (INFO by default, DEBUG in development), initializes
    the database, creates the engine, sets up telemetry (if enabled), registers blueprints
    (admin, blog, SEO), and configures minification and CSRF protection.

    Args:
        config: Application configuration object
        extra_plugin_bases: Capability base classes the application registers for its
            own plugin ecosystem, in addition to platzky's built-in ``PLUGIN_BASES``.
            Plugins cannot register capabilities; only the application composing them can.
        extra_plugins_entrypoints: Entry-point groups the application registers for
            plugin discovery, in addition to ``platzky.plugins``.
        extra_content_types: Content types the application produces beyond platzky's own,
            so its plugins can opt in to them through ``accepted_content_types``.
            The application's own contribution; a plugin declares any type it introduces
            through ``PluginBase.provides_content_types``.
        development: Whether this is a development machine, which ``platzky run`` sets and a
            production server leaves false. Enables Flask's debug mode and the shortcuts
            that are unsafe in production, such as fake login. Outside development the app
            trusts X-Forwarded-Proto from one proxy, marks the session cookie secure and
            sends HSTS on HTTPS responses.

    Returns:
        Fully configured Engine instance ready to serve requests

    Raises:
        ImportError: If telemetry is enabled but OpenTelemetry packages are not installed
        ValueError: If telemetry configuration is invalid
    """
    # LOG_LEVEL is the application's own setting, so it covers every logger, not just platzky's.
    _configure_logging(config.log_level or ("DEBUG" if development else _DEFAULT_LOG_LEVEL))

    db = get_db(config.db)
    engine = create_engine(
        config, db, extra_plugin_bases, extra_plugins_entrypoints, extra_content_types
    )
    # Set here rather than read from FLASK_DEBUG, so how the app was started decides.
    engine.debug = development

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

    # After telemetry, so ProxyFix wraps its middleware and it sees the forwarded scheme.
    if not development:
        _enforce_https(engine)

    # Register built-in shortcodes (image, link) as the first ContentTransformerPluginBase,
    # so they run before any plugin filter and appear on the admin help page.
    _builtin_transformer = _BuiltinShortcodeTransformer({})
    # Inserted rather than registered, because register_plugin appends and this one must
    # run first.
    engine.plugins[ContentTransformerPluginBase].insert(0, _builtin_transformer)
    # Self-granted, not site-owner config: the builtins are not opt-in, so the plugin's own
    # declaration stands in for the grant. They route through the same gate as everything else.
    engine.content_transformers.grant(
        _builtin_transformer, frozenset(_builtin_transformer.accepted_content_types)
    )
    engine.shortcodes.update(_builtin_transformer.shortcodes)

    _other_transformers = [
        p for p in engine.get_plugins(ContentTransformerPluginBase) if p is not _builtin_transformer
    ]
    _new_shortcodes, _new_extensions = _gather_shortcodes_and_extensions(
        _other_transformers, engine.shortcodes
    )
    engine.shortcodes.update(_new_shortcodes)
    for _ext in _new_extensions:
        engine.jinja_env.add_extension(_ext)

    if engine.is_enabled(FakeLogin):
        if not development:
            raise RuntimeError(
                "SECURITY ERROR: Cannot register FakeLoginPlugin in production. "
                "Fake login is only available in development, i.e. under `platzky run`."
            )
        from platzky.debug.fake_login import FakeLoginPlugin

        engine.register_plugin(FakeLoginPlugin({}), "fake_login")

    login_blueprint = login.create_login_blueprint(
        login_plugins=engine.get_plugins(LoginPluginBase),
    )
    admin_blueprint = admin.create_admin_blueprint(
        cms_modules=engine.cms_modules,
        shortcodes=list(engine.shortcodes.values()),
        plugin_infos=engine.get_plugin_infos(),
    )

    blog_blueprint = blog.create_blog_blueprint(
        blog_repository=engine.db.blog,
        blog_prefix=config.blog_prefix,
        locale_func=engine.get_locale,
        content_transformer=engine.transform_content,
    )
    engine.register_blueprint(login_blueprint)
    engine.register_blueprint(admin_blueprint)
    engine.register_blueprint(blog_blueprint)
    # Platzky's own routes are all registered here; the SEO blueprint is not a home page.
    languages = config.language_routing.languages
    engine.home_page_paths = resolve_home_page_paths(
        engine.url_map, engine.home_page_paths, languages
    )
    warn_about_languages_without_a_home_page(languages, engine.home_page_paths)
    seo_blueprint = seo.create_seo_blueprint(
        config=engine.config,
        routing=config.language_routing,
        sitemap_providers=engine.sitemap_providers,
        url_for_language=engine.url_for_language,
    )
    engine.register_blueprint(seo_blueprint)

    Minify(app=engine, html=True, js=True, cssless=True)
    CSRFProtect(app=engine)
    return engine


def create_app(config_path: str, development: bool = False) -> Engine:
    """Create a Platzky application from a YAML configuration file.

    Convenience function that loads configuration from a YAML file and
    creates the application.

    Args:
        config_path: Path to the YAML configuration file
        development: Whether this is a development machine; ``platzky run`` sets it

    Returns:
        Fully configured Engine instance ready to serve requests

    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        yaml.YAMLError: If the configuration file contains invalid YAML
        ValidationError: If the configuration doesn't match the expected schema
    """
    config = Config.parse_yaml(config_path)
    return create_app_from_config(config, development=development)
