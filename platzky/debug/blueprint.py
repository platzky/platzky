"""Debug-only Flask blueprint."""

from typing import Any

from flask import Blueprint
from flask.sansio.app import App


class DebugBlueprint(Blueprint):
    """A Blueprint that can only be registered on apps in debug/testing mode.

    Raises RuntimeError during registration if the app is not in debug or testing mode.
    This provides a structural guarantee that debug-only routes cannot be accidentally
    enabled in production.
    """

    def register(self, app: App, options: dict[str, Any]) -> None:
        """Register the blueprint, but only if app is in debug/testing mode."""
        if not (app.config.get("DEBUG") or app.config.get("TESTING")):
            raise RuntimeError(
                f"SECURITY ERROR: Cannot register DebugBlueprint '{self.name}' in production. "
                f"DEBUG and TESTING are both False. "
                f"Set DEBUG: true or TESTING: true in your config."
            )
        super().register(app, options)
