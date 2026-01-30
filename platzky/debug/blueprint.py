"""Debug-only Platzky blueprint."""

import os
from typing import Any

from flask import Blueprint
from flask.sansio.app import App
from typing_extensions import override

_FLASK_DEBUG_TRUTHY = {"1", "true", "yes"}


def _is_flask_debug_env() -> bool:
    """Check if FLASK_DEBUG environment variable indicates debug mode.

    Flask CLI sets this env var before calling the app factory, so it
    reflects ``--debug`` even though ``app.config["DEBUG"]`` may not yet.
    """
    return os.environ.get("FLASK_DEBUG", "").lower() in _FLASK_DEBUG_TRUTHY


class DebugBlueprintProductionError(RuntimeError):
    """Raised when a DebugBlueprint is registered on a production app."""

    def __init__(self, blueprint_name: str) -> None:
        super().__init__(
            f"SECURITY ERROR: Cannot register DebugBlueprint '{blueprint_name}' in production. "
            f"DEBUG and TESTING are both False. "
            f"Set DEBUG: true or TESTING: true in your config, "
            f"or use flask --debug."
        )


class DebugBlueprint(Blueprint):
    """A Blueprint that can only be registered on apps in debug/testing mode.

    Raises DebugBlueprintProductionError during registration if the app is not
    in debug or testing mode. This provides a structural guarantee that debug-only
    routes cannot be accidentally enabled in production.

    Checks ``app.config["DEBUG"]``, ``app.config["TESTING"]``, and the
    ``FLASK_DEBUG`` environment variable (set by ``flask --debug`` before
    the app factory is called).
    """

    @override
    def register(self, app: App, options: dict[str, Any]) -> None:
        """Register the blueprint, but only if app is in debug/testing mode."""
        if not (app.config.get("DEBUG") or app.config.get("TESTING") or _is_flask_debug_env()):
            raise DebugBlueprintProductionError(self.name)
        super().register(app, options)
