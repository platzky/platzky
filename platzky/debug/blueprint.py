"""Debug-only Platzky blueprint."""

from typing import Any

from flask import Blueprint
from flask.sansio.app import App
from typing_extensions import override


class DebugBlueprintProductionError(RuntimeError):
    """Raised when a DebugBlueprint is registered on a production app."""

    def __init__(self, blueprint_name: str) -> None:
        super().__init__(
            f"SECURITY ERROR: Cannot register DebugBlueprint '{blueprint_name}' in production. "
            f"DEBUG and TESTING are both False. "
            f"Set DEBUG: true or TESTING: true in your config."
        )


class DebugBlueprint(Blueprint):
    """A Blueprint that can only be registered on apps in debug/testing mode.

    Raises DebugBlueprintProductionError during registration if the app is not
    in debug or testing mode. This provides a structural guarantee that debug-only
    routes cannot be accidentally enabled in production.
    """

    @override
    def register(self, app: App, options: dict[str, Any]) -> None:
        """Register the blueprint, but only if app is in debug/testing mode."""
        if not (app.config.get("DEBUG") or app.config.get("TESTING")):
            raise DebugBlueprintProductionError(self.name)
        super().register(app, options)
