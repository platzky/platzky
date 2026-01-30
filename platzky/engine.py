"""Flask application engine with notification support."""

import logging
import os
import threading
from collections.abc import Callable
from concurrent.futures import Future, TimeoutError
from typing import Any

from flask import Blueprint, Flask, Response, jsonify, make_response, request, session
from flask_babel import Babel

from platzky.attachment import AttachmentProtocol, create_attachment_class
from platzky.config import Config
from platzky.db.db import DB
from platzky.feature_flags import Flag, flags_to_dict, get_all_flags_metadata
from platzky.models import CmsModule
from platzky.notifier import Notifier, NotifierWithAttachments

logger = logging.getLogger(__name__)


class Engine(Flask):
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
        self._platzky_config = config  # Store for typed access
        self.db = db
        self.Attachment: type[AttachmentProtocol] = create_attachment_class(config.attachment)
        self.notifiers: list[Notifier] = []
        self.notifiers_with_attachments: list[NotifierWithAttachments] = []
        self.login_methods = []
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

        # JSON provider for frozenset[type[Flag]] serialization (Jinja ``tojson`` filter)
        original_default = self.json.default  # type: ignore[reportAttributeAccessIssue]

        def extended_default(o: object) -> object:
            if isinstance(o, frozenset):
                return flags_to_dict(o, type(config).get_flag_types())
            return original_default(o)

        self.json.default = staticmethod(extended_default)  # type: ignore[reportAttributeAccessIssue]

        self.cms_modules: list[CmsModule] = []
        # TODO add plugins as CMS Module - all plugins should be visible from
        # admin page at least as configuration

    def notify(self, message: str, attachments: list[AttachmentProtocol] | None = None) -> None:
        """Send a notification to all registered notifiers.

        Args:
            message: The notification message text.
            attachments: Optional list of Attachment objects created via engine.Attachment().
        """
        for notifier in self.notifiers:
            notifier(message)
        for notifier in self.notifiers_with_attachments:
            notifier(message, attachments=attachments)

    def add_notifier(self, notifier: Notifier) -> None:
        """Register a simple notifier (message only).

        Args:
            notifier: A callable that accepts a message string.
        """
        self.notifiers.append(notifier)

    def add_notifier_with_attachments(self, notifier: NotifierWithAttachments) -> None:
        """Register a notifier that supports attachments.

        Args:
            notifier: A callable that accepts message and optional attachments.
        """
        self.notifiers_with_attachments.append(notifier)

    def add_cms_module(self, module: CmsModule):
        """Add a CMS module to the modules list."""
        self.cms_modules.append(module)

    # TODO login_method should be interface
    def add_login_method(self, login_method: Callable[[], str]) -> None:
        self.login_methods.append(login_method)

    def add_dynamic_body(self, body: str):
        self.dynamic_body += body

    def add_dynamic_head(self, body: str):
        self.dynamic_head += body

    def get_locale(self) -> str:
        languages = self.config.get("LANGUAGES", {}).keys()

        session_lang = session.get("language")
        if isinstance(session_lang, str) and session_lang in languages:
            lang = session_lang
        else:
            lang = request.accept_languages.best_match(languages) or "en"

        session["language"] = lang
        return lang

    def is_enabled(self, flag_type: type[Flag]) -> bool:
        """Check whether a feature flag is enabled.

        This is the primary API for flag checks.

        Args:
            flag_type: A Flag subclass registered in Config._flag_types.

        Returns:
            True if the flag is enabled.
        """
        return flag_type in self._platzky_config.feature_flags

    def add_health_check(self, name: str, check_function: Callable[[], None]) -> None:
        """Register a health check function"""
        if not callable(check_function):
            raise TypeError(f"check_function must be callable, got {type(check_function)}")
        self.health_checks.append((name, check_function))

    def get_all_feature_flags(self) -> dict[str, dict[str, bool | str]]:
        """Return all feature flags with their values and metadata.

        Returns:
            Dict mapping flag alias to metadata dict with keys:
            ``value``, ``description``, ``default``, ``alias``.
            Useful for admin panels and debugging.
        """
        return get_all_flags_metadata(
            self._platzky_config.feature_flags,
            type(self._platzky_config).get_flag_types(),
        )

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
