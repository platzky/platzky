"""Flask application engine with notification support."""

import inspect
import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any

from flask import Blueprint, Flask, jsonify, make_response, request, session
from flask_babel import Babel

from platzky.attachment import Attachment
from platzky.config import Config
from platzky.db.db import DB
from platzky.models import CmsModule
from platzky.notification_result import (
    AttachmentDropError,
    AttachmentDropPolicy,
    NotificationResult,
    NotifierResult,
)
from platzky.notifier import Notifier

# =============================================================================
# Backward Compatibility Re-exports
# =============================================================================
# These re-exports ensure existing code continues to work:
#   from platzky.engine import AttachmentDropPolicy, NotificationResult, etc.
#
# New code should import from the specific module:
#   from platzky.notification_result import AttachmentDropPolicy

# Re-export for backward compatibility (already imported above, just making explicit)
AttachmentDropError = AttachmentDropError
AttachmentDropPolicy = AttachmentDropPolicy
NotificationResult = NotificationResult
NotifierResult = NotifierResult

logger = logging.getLogger(__name__)


class Engine(Flask):
    def __init__(
        self,
        config: Config,
        db: DB,
        import_name: str,
        attachment_drop_policy: AttachmentDropPolicy = AttachmentDropPolicy.WARN,
    ) -> None:
        """Initialize the Engine.

        Args:
            config: Application configuration.
            db: Database instance.
            import_name: Name of the application module.
            attachment_drop_policy: Policy for handling attachments when a notifier
                doesn't support them. Defaults to WARN for backward compatibility.

                - WARN: Log a warning and proceed without attachments.
                  WARNING: This may lead to silent data loss if attachments are critical.
                - ERROR: Raise AttachmentDropError, preventing the notification.
                - SKIP_NOTIFIER: Skip the notifier entirely and log a warning.
        """
        super().__init__(import_name)
        self.config.from_mapping(config.model_dump(by_alias=True))
        self.db = db
        self.notifiers: list[Notifier] = []
        self._notifier_capability_cache: dict[int, bool] = {}
        self.attachment_drop_policy = attachment_drop_policy
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

        self.cms_modules: list[CmsModule] = []
        # TODO add plugins as CMS Module - all plugins should be visible from
        # admin page at least as configuration

    def notify(
        self, message: str, attachments: list[Attachment] | None = None
    ) -> NotificationResult:
        """Send a notification to all registered notifiers.

        Args:
            message: The notification message text.
            attachments: Optional list of validated Attachment objects.

        Returns:
            NotificationResult with details about which notifiers received
            attachments, which didn't, and which were skipped.

        Raises:
            AttachmentDropError: If attachment_drop_policy is ERROR and a notifier
                doesn't support attachments.
        """
        result = NotificationResult()
        attachment_count = len(attachments) if attachments else 0

        for notifier in self.notifiers:
            notifier_result = self._notify_single(notifier, message, attachments, attachment_count)
            result.notifier_results.append(notifier_result)

        return result

    def _notify_single(
        self,
        notifier: Notifier,
        message: str,
        attachments: list[Attachment] | None,
        attachment_count: int,
    ) -> NotifierResult:
        """Send notification to a single notifier and return the result."""
        notifier_name = getattr(notifier, "__name__", type(notifier).__name__)
        supports_attachments = self._notifier_supports_attachments(notifier)

        if supports_attachments:
            notifier(message, attachments=attachments)
            return NotifierResult(
                notifier_name=notifier_name,
                received_attachments=bool(attachments),
            )

        if not attachments:
            notifier(message)
            return NotifierResult(notifier_name=notifier_name)

        # Notifier doesn't support attachments and we have attachments
        return self._handle_attachment_drop(notifier, notifier_name, message, attachment_count)

    def _handle_attachment_drop(
        self,
        notifier: Notifier,
        notifier_name: str,
        message: str,
        attachment_count: int,
    ) -> NotifierResult:
        """Handle the case where a notifier doesn't support attachments."""
        if self.attachment_drop_policy == AttachmentDropPolicy.ERROR:
            raise AttachmentDropError(notifier_name, attachment_count)

        if self.attachment_drop_policy == AttachmentDropPolicy.SKIP_NOTIFIER:
            logger.warning(
                "Skipping notifier %s: does not support attachments "
                "(%d attachment(s) would be dropped)",
                notifier_name,
                attachment_count,
            )
            return NotifierResult(notifier_name=notifier_name, skipped=True)

        # WARN policy (default)
        logger.warning(
            "Notifier %s does not support attachments, " "%d attachment(s) will be dropped",
            notifier_name,
            attachment_count,
        )
        notifier(message)
        return NotifierResult(
            notifier_name=notifier_name,
            attachments_dropped=attachment_count,
        )

    def _notifier_supports_attachments(self, notifier: Notifier) -> bool:
        """Check if a notifier supports attachments parameter.

        Results are cached using id(notifier) as key to avoid repeated
        inspect.signature() calls which are expensive.
        """
        notifier_id = id(notifier)
        if notifier_id in self._notifier_capability_cache:
            return self._notifier_capability_cache[notifier_id]

        try:
            sig = inspect.signature(notifier)
        except (ValueError, TypeError) as e:
            logger.warning(
                "Failed to inspect signature of notifier %s: %s",
                getattr(notifier, "__name__", type(notifier).__name__),
                e,
            )
            self._notifier_capability_cache[notifier_id] = False
            return False
        else:
            result = "attachments" in sig.parameters
            self._notifier_capability_cache[notifier_id] = result
            return result

    def clear_notifier_cache(self) -> None:
        """Clear the notifier capability cache.

        This should be called if notifiers are modified at runtime
        or replaced with new instances.
        """
        self._notifier_capability_cache.clear()

    def add_notifier(self, notifier: Notifier) -> None:
        """Register a notifier to receive notifications.

        Args:
            notifier: A callable conforming to the Notifier protocol.
        """
        self.notifiers.append(notifier)

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
        domain = request.headers.get("Host", "localhost")
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

    def add_health_check(self, name: str, check_function: Callable[[], None]) -> None:
        """Register a health check function"""
        if not callable(check_function):
            raise TypeError(f"check_function must be callable, got {type(check_function)}")
        self.health_checks.append((name, check_function))

    def _register_default_health_endpoints(self) -> None:
        """Register default health endpoints."""
        health_bp = Blueprint("health", __name__)
        health_check_timeout = 10  # seconds

        def run_health_check(
            executor: ThreadPoolExecutor,
            check_func: Callable[[], None],
            timeout: int,
        ) -> str:
            """Run a health check with timeout, returning status string."""
            future = executor.submit(check_func)
            try:
                future.result(timeout=timeout)
                return "ok"
            except TimeoutError:
                return "failed: timeout"
            except Exception as e:
                return f"failed: {e!s}"

        @health_bp.route("/health/liveness")
        def liveness():
            """Simple liveness check - is the app running?"""
            return jsonify({"status": "alive"}), 200

        @health_bp.route("/health/readiness")
        def readiness():
            """Readiness check - can the app serve traffic?"""
            health_status: dict[str, Any] = {"status": "ready", "checks": {}}

            all_checks = [("database", self.db.health_check), *self.health_checks]

            executor = ThreadPoolExecutor(max_workers=1)
            try:
                for check_name, check_func in all_checks:
                    status = run_health_check(executor, check_func, health_check_timeout)
                    health_status["checks"][check_name] = status
                    if status != "ok":
                        health_status["status"] = "not_ready"
            finally:
                executor.shutdown(wait=False)

            status_code = 200 if health_status["status"] == "ready" else 503
            return make_response(jsonify(health_status), status_code)

        @health_bp.route("/health")
        def health():
            """Simple /health alias for liveness."""
            return liveness()

        self.register_blueprint(health_bp)
