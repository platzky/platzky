"""Flask application engine with notification support."""

import logging
import os
import threading
from collections import defaultdict
from collections.abc import Callable, Sequence
from concurrent.futures import Future, TimeoutError
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from platzky.plugin.plugin import PluginBase

import deprecation
from flask import (
    Blueprint,
    Flask,
    Response,
    jsonify,
    make_response,
    request,
    session,
)
from flask_babel import Babel

from platzky.attachment import AttachmentProtocol, create_attachment_class
from platzky.config import Config
from platzky.content_types import ContentType
from platzky.db.db import DB
from platzky.feature_flags import FeatureFlag
from platzky.models import CmsModule
from platzky.notification_topics import NotificationTopic
from platzky.notifier import Notifier, NotifierWithAttachments
from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.plugin.notifier import AttachmentNotifierPluginBase, NotifierPluginBase
from platzky.shortcodes import Shortcode

logger = logging.getLogger(__name__)


def _is_safe_locale_dir(locale_dir: str, plugin_instance: "PluginBase") -> bool:
    """Validate that a locale directory is safe to use.

    Prevents malicious plugins from exposing arbitrary filesystem paths
    by ensuring the locale directory is within the plugin's module directory.
    """
    import inspect

    if not os.path.isdir(locale_dir):
        return False

    module = inspect.getmodule(plugin_instance.__class__)
    if module is None or not hasattr(module, "__file__") or module.__file__ is None:
        return False

    normalized_path = os.path.normpath(locale_dir)
    if ".." in normalized_path.split(os.sep):
        logger.warning("Rejected locale path with .. components: %s", locale_dir)
        return False

    locale_path = os.path.realpath(locale_dir)
    module_path = os.path.realpath(os.path.dirname(module.__file__))

    if not locale_path.startswith(module_path + os.sep):
        if locale_path != module_path:
            return False

    return True


_PLUGIN_CAPABILITY_BASES: tuple[type, ...] = (NotifierPluginBase, ContentTransformerPluginBase)


class Engine(Flask):
    """Flask subclass composing database, plugins, notifications, and health checks."""

    def __init__(
        self,
        config: Config,
        db: DB,
        import_name: str,
    ) -> None:
        """Initialize the Engine.

        Args:
            config: Application configuration.
            db: Database instance.
            import_name: Name of the application module.
        """
        super().__init__(import_name)
        self.config.from_mapping(config.model_dump(by_alias=True))
        self.config["FEATURE_FLAGS"] = config.feature_flags
        self.db = db
        self.Attachment: type[AttachmentProtocol] = create_attachment_class(config.attachment)
        self.plugins: defaultdict[type, list[Any]] = defaultdict(list)
        self.loaded_plugins: list[Any] = []
        self._notifier_topic_allowlist: dict[NotifierPluginBase, frozenset[NotificationTopic]] = {}
        self._content_transformer_allowlist: dict[
            ContentTransformerPluginBase, frozenset[ContentType]
        ] = {}
        self.shortcodes: dict[str, Shortcode] = {}

        # Deprecated — kept for backward compatibility until v2.0
        self._notifiers: list[Notifier] = []
        self._notifiers_with_attachments: list[NotifierWithAttachments] = []

        self.login_methods: list[Callable[[], str]] = []
        self.dynamic_body = ""
        self.dynamic_head = ""
        self.health_checks: list[tuple[str, Callable[[], None]]] = []
        self.telemetry_instrumented: bool = False
        directory = os.path.dirname(os.path.realpath(__file__))
        locale_dir = os.path.join(directory, "locale")
        config.translation_directories.append(locale_dir)
        babel_translation_directories = ";".join(config.translation_directories)
        self.babel = Babel(
            self,
            locale_selector=self.get_locale,
            default_translation_directories=babel_translation_directories,
        )
        self._register_default_health_endpoints()

        self.cms_modules: list[CmsModule] = []

    def get_plugins(self, plugin_type: type) -> list[Any]:
        """Return all registered plugins of the given capability type."""
        return self.plugins.get(plugin_type, [])

    def get_plugin_infos(self) -> list[Any]:
        """Return PluginInfo metadata for all loaded plugins."""
        return [plugin.get_info() for plugin in self.loaded_plugins]

    def notify(
        self,
        message: str,
        topic: NotificationTopic = "general",
        attachments: Sequence[AttachmentProtocol] = (),
        receiver: str = "",
    ) -> None:
        """Send a notification to all registered notifiers.

        Args:
            message: The notification message text.
            topic: Notification topic for routing (default ``"general"``).
            attachments: Attachments to include; empty sequence if none.
            receiver: Target recipient identifier; empty string means broadcast.
        """
        # Legacy path
        for notifier in self._notifiers:
            notifier(message)
        for notifier in self._notifiers_with_attachments:
            notifier(message, attachments=attachments)

        # New capability-based path
        for plugin in self.get_plugins(NotifierPluginBase):
            if topic not in plugin.accepted_topics:
                continue
            if topic not in self._notifier_topic_allowlist.get(plugin, frozenset()):
                continue
            if isinstance(plugin, AttachmentNotifierPluginBase):
                plugin.notify_with_attachments(message, topic, attachments, receiver)
            else:
                plugin.notify(message, topic, receiver)

    @deprecation.deprecated(
        deprecated_in="1.5.0",
        removed_in="2.0.0",
        details="Use NotifierPluginBase subclass instead.",
    )
    def add_notifier(self, notifier: Notifier) -> None:
        """Register a simple notifier (message only).

        Deprecated: implement NotifierPluginBase instead.
        """
        self._notifiers.append(notifier)

    @deprecation.deprecated(
        deprecated_in="1.5.0",
        removed_in="2.0.0",
        details="Use NotifierPluginBase subclass instead.",
    )
    def add_notifier_with_attachments(self, notifier: NotifierWithAttachments) -> None:
        """Register a notifier that supports attachments.

        Deprecated: implement NotifierPluginBase instead.
        """
        self._notifiers_with_attachments.append(notifier)

    def transform_content(self, content: str, content_type: ContentType) -> str:
        """Apply all registered content-filter plugins for the given content type.

        Checks plugin's declared ``accepted_content_types`` first, then the
        engine-enforced allowlist set via ``set_content_transformer_allowlist``.
        """
        for plugin in self.get_plugins(ContentTransformerPluginBase):
            if content_type not in plugin.accepted_content_types:
                continue
            if content_type not in self._content_transformer_allowlist.get(plugin, frozenset()):
                continue
            content = plugin.transform_content(content)
        return content

    def set_content_transformer_allowlist(
        self, plugin: ContentTransformerPluginBase, allowed_types: frozenset[ContentType]
    ) -> None:
        """Register engine-enforced content-type allowlist for a content-transformer plugin.

        Empty frozenset blocks all content types. Plugin absent from the allowlist is also blocked.
        Called by the plugin loader; not intended to be called from plugin code.
        """
        self._content_transformer_allowlist[plugin] = allowed_types

    def register_plugin_capabilities(self, instance: "PluginBase", plugin_name: str) -> None:
        """Register a plugin instance under all matching capability keys.

        Each recognised capability base class becomes a key in ``self.plugins`` so the
        engine can look up e.g. all NotifierPluginBase plugins without knowing concrete types.
        Plugins that don't match any capability are stored under PluginBase.
        """
        from platzky.plugin.plugin import PluginBase

        registered = False
        for base in _PLUGIN_CAPABILITY_BASES:
            if isinstance(instance, base):
                self.plugins[base].append(instance)
                registered = True
                logger.debug(
                    "Registered plugin '%s' under capability %s", plugin_name, base.__name__
                )

        self.plugins[type(instance)].append(instance)

        if not registered:
            self.plugins[PluginBase].append(instance)

    def register_plugin_locale(self, plugin_instance: "PluginBase", plugin_name: str) -> None:
        """Register plugin's locale directory with Babel if it exists."""
        locale_dir = plugin_instance.get_locale_dir()
        if locale_dir is None:
            return

        if not _is_safe_locale_dir(locale_dir, plugin_instance):
            logger.warning(
                "Skipping locale directory for plugin %s: path validation failed: %s",
                plugin_name,
                locale_dir,
            )
            return

        babel_config = self.extensions.get("babel")
        if babel_config and locale_dir not in babel_config.translation_directories:
            babel_config.translation_directories.append(locale_dir)
            logger.info("Registered locale directory for plugin %s: %s", plugin_name, locale_dir)

    def load_plugin(
        self,
        plugin_class: "type[PluginBase]",
        plugin_config: dict[str, Any],
        plugin_name: str,
        allowed_topics: frozenset[NotificationTopic] = frozenset(),
        allowed_content_types: frozenset[ContentType] = frozenset(),
    ) -> "Engine":
        """Instantiate and register a class-based plugin. Returns the (possibly replaced) engine.

        Args:
            plugin_class: The plugin class to instantiate.
            plugin_config: Configuration dict passed to the plugin constructor.
            plugin_name: Human-readable name used in log messages.
            allowed_topics: Topic allowlist for notifier plugins. ``frozenset()`` blocks all topics;
                a non-empty frozenset restricts to those topics.
            allowed_content_types: Content-type allowlist for transformer plugins.
                ``frozenset()`` blocks all types; a non-empty frozenset restricts.

        Returns:
            The (possibly replaced) engine after loading the plugin.
        """
        from platzky.plugin.plugin import PluginBase

        plugin_instance = plugin_class(plugin_config)
        # MRO-based identity check: every class inherits process() from PluginBase so
        # hasattr() would always return True.  Comparing unbound method objects via `is`
        # detects a genuine override without invoking the deprecation warning that calling
        # the base no-op implementation would raise.
        app = (
            plugin_instance.process(self)
            if type(plugin_instance).process is not PluginBase.process
            else self
        )
        app.loaded_plugins.append(plugin_instance)
        app.register_plugin_locale(plugin_instance, plugin_name)
        app.register_plugin_capabilities(plugin_instance, plugin_name)
        if isinstance(plugin_instance, NotifierPluginBase):
            app.set_notifier_allowlist(plugin_instance, allowed_topics)
        if isinstance(plugin_instance, ContentTransformerPluginBase):
            app.set_content_transformer_allowlist(plugin_instance, allowed_content_types)
        logger.info("Processed class-based plugin: %s", plugin_name)
        return app

    def set_notifier_allowlist(
        self, plugin: NotifierPluginBase, allowed_topics: frozenset[NotificationTopic]
    ) -> None:
        """Register engine-enforced topic allowlist for a notifier.

        Empty frozenset blocks all topics. Plugin absent from the allowlist is also blocked.
        Called by the plugin loader; not accessible to plugin code.
        """
        self._notifier_topic_allowlist[plugin] = allowed_topics

    def add_cms_module(self, module: CmsModule) -> None:
        """Add a CMS module to the modules list."""
        self.cms_modules.append(module)

    def add_login_method(self, login_method: Callable[[], str]) -> None:
        """Register a login method callable."""
        self.login_methods.append(login_method)

    def add_dynamic_body(self, body: str) -> None:
        """Append HTML to the dynamic body section rendered in templates."""
        self.dynamic_body += body

    def add_dynamic_head(self, head: str) -> None:
        """Append HTML to the dynamic head section rendered in templates."""
        self.dynamic_head += head

    def get_locale(self) -> str:
        """Return the current locale based on session or browser preferences."""
        languages = self.config.get("LANGUAGES", {}).keys()

        session_lang = session.get("language")
        if isinstance(session_lang, str) and session_lang in languages:
            lang = session_lang
        else:
            lang = request.accept_languages.best_match(languages) or "en"

        session["language"] = lang
        return lang

    def is_enabled(self, flag: FeatureFlag) -> bool:
        """Check whether a feature flag is enabled.

        This is the primary API for flag checks.

        Args:
            flag: A FeatureFlag instance.

        Returns:
            True if the flag is enabled.
        """
        return flag in self.config["FEATURE_FLAGS"]

    def add_health_check(self, name: str, check_function: Callable[[], None]) -> None:
        """Register a health check function."""
        if not callable(check_function):
            raise TypeError(f"check_function must be callable, got {type(check_function)}")
        self.health_checks.append((name, check_function))

    def _register_default_health_endpoints(self) -> None:
        """Register default health endpoints."""
        health_bp = Blueprint("health", __name__)
        health_check_timeout = 10  # seconds

        def run_health_check(
            check_func: Callable[[], None],
            timeout: int,
        ) -> str:
            """Run a health check with timeout using a daemon thread.

            Uses daemon threads so stuck checks don't prevent app shutdown.
            Note: Health checks should implement their own internal timeouts
            for proper resource cleanup - the external timeout only prevents
            blocking the response, but the check continues running.
            """
            future: Future[None] = Future()

            def run() -> None:
                """Execute the health check and resolve the future."""
                try:
                    check_func()
                    future.set_result(None)
                except Exception as e:
                    future.set_exception(e)

            thread = threading.Thread(target=run, daemon=True)
            thread.start()

            try:
                future.result(timeout=timeout)
            except TimeoutError:
                return "failed: timeout"
            except Exception as e:
                logger.exception("Health check failed")
                return f"failed: {e!s}"
            else:
                return "ok"

        @health_bp.route("/health/liveness")
        def liveness() -> tuple[Response, int]:
            """Simple liveness check - is the app running?"""
            return jsonify({"status": "alive"}), 200

        @health_bp.route("/health/readiness")
        def readiness() -> Response:
            """Readiness check - can the app serve traffic?"""
            health_status: dict[str, Any] = {"status": "ready", "checks": {}}

            all_checks = [("database", self.db.health_check), *self.health_checks]

            for check_name, check_func in all_checks:
                status = run_health_check(check_func, health_check_timeout)
                health_status["checks"][check_name] = status
                if status != "ok":
                    health_status["status"] = "not_ready"

            status_code = 200 if health_status["status"] == "ready" else 503
            return make_response(jsonify(health_status), status_code)

        @health_bp.route("/health")
        def health() -> tuple[Response, int]:
            """Simple /health alias for liveness."""
            return liveness()

        self.register_blueprint(health_bp)
