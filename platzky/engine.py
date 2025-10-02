import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Callable, Dict, List, Tuple

from flask import Blueprint, Flask, jsonify, make_response, request, session
from flask_babel import Babel

from platzky.config import Config
from platzky.models import CmsModule


class Engine(Flask):
    def __init__(self, config: Config, db, import_name):
        super().__init__(import_name)
        self.config.from_mapping(config.model_dump(by_alias=True))
        self.db = db
        self.notifiers = []
        self.login_methods = []
        self.dynamic_body = ""
        self.dynamic_head = ""
        self.health_checks: List[Tuple[str, Callable[[], None]]] = []
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

        self.cms_modules: List[CmsModule] = []
        # TODO add plugins as CMS Module - all plugins should be visible from
        # admin page at least as configuration

    def notify(self, message: str):
        for notifier in self.notifiers:
            notifier(message)

    def add_notifier(self, notifier):
        self.notifiers.append(notifier)

    def add_cms_module(self, module: CmsModule):
        """Add a CMS module to the modules list."""
        self.cms_modules.append(module)

    # TODO login_method should be interface
    def add_login_method(self, login_method):
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

    def _register_default_health_endpoints(self):
        """Register default health endpoints"""

        health_bp = Blueprint("health", __name__)
        HEALTH_CHECK_TIMEOUT = 10  # seconds

        @health_bp.route("/health/liveness")
        def liveness():
            """Simple liveness check - is the app running?"""
            return jsonify({"status": "alive"}), 200

        @health_bp.route("/health/readiness")
        def readiness():
            """Readiness check - can the app serve traffic?"""
            health_status: Dict[str, Any] = {"status": "ready", "checks": {}}
            status_code = 200

            executor = ThreadPoolExecutor(max_workers=1)
            try:
                # Database health check with timeout
                future = executor.submit(self.db.health_check)
                try:
                    future.result(timeout=HEALTH_CHECK_TIMEOUT)
                    health_status["checks"]["database"] = "ok"
                except TimeoutError:
                    health_status["checks"]["database"] = "failed: timeout"
                    health_status["status"] = "not_ready"
                    status_code = 503
                except Exception as e:
                    health_status["checks"]["database"] = f"failed: {e!s}"
                    health_status["status"] = "not_ready"
                    status_code = 503

                # Run application-registered health checks
                for check_name, check_func in self.health_checks:
                    future = executor.submit(check_func)
                    try:
                        future.result(timeout=HEALTH_CHECK_TIMEOUT)
                        health_status["checks"][check_name] = "ok"
                    except TimeoutError:
                        health_status["checks"][check_name] = "failed: timeout"
                        health_status["status"] = "not_ready"
                        status_code = 503
                    except Exception as e:
                        health_status["checks"][check_name] = f"failed: {e!s}"
                        health_status["status"] = "not_ready"
                        status_code = 503
            finally:
                # Shutdown without waiting if any futures are still running
                executor.shutdown(wait=False)

            return make_response(jsonify(health_status), status_code)

        # Simple /health alias for liveness
        @health_bp.route("/health")
        def health():
            return liveness()

        self.register_blueprint(health_bp)
