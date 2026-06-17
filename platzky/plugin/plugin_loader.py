"""Plugin discovery, loading, and lifecycle management."""

from __future__ import annotations

import importlib.metadata
import inspect
import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from platzky.plugin.plugin import PluginBase, PluginError

if TYPE_CHECKING:
    from platzky.engine import Engine

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "platzky.plugins"


def _discover_entry_points() -> tuple[dict[str, type[PluginBase]], dict[str, Exception]]:
    discovered: dict[str, type[PluginBase]] = {}
    failed: dict[str, Exception] = {}
    for entry_point in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP):
        try:
            plugin_class = entry_point.load()
        except Exception as e:
            logger.exception("Failed to load entry point '%s'", entry_point.name)
            failed[entry_point.name] = e
            continue

        if not (inspect.isclass(plugin_class) and issubclass(plugin_class, PluginBase)):
            logger.warning(
                "Entry point '%s' does not point to a PluginBase subclass, skipping",
                entry_point.name,
            )
            continue

        if entry_point.name in discovered:
            raise ValueError(
                f"Duplicate plugin entry-point name '{entry_point.name}': "
                f"already registered as {discovered[entry_point.name]}, "
                f"conflicting class {plugin_class}"
            )
        discovered[entry_point.name] = plugin_class
        logger.debug("Discovered plugin '%s' via entry points", entry_point.name)

    return discovered, failed


def plugify(app: Engine) -> Engine:
    """Load and initialise plugins configured in the database.

    Plugins must declare a ``platzky.plugins`` entry point in their package metadata.

    Args:
        app: Platzky Engine instance

    Returns:
        Platzky Engine with all configured plugins loaded

    Raises:
        PluginError: if a configured plugin cannot be loaded or initialised
    """
    try:
        plugins_data = app.db.get_plugins_data()
    except ValidationError as e:
        raise PluginError(f"Invalid plugin configuration in database: {e}") from e

    discovered, failed_entry_points = _discover_entry_points()

    for plugin_name, plugin_config in plugins_data.items():
        if not plugin_config.is_active:
            logger.debug("Plugin '%s' is inactive, skipping.", plugin_name)
            continue
        try:
            if plugin_name in discovered:
                plugin_class = discovered[plugin_name]
                app = app.load_plugin(plugin_class, plugin_name, plugin_config)
            elif plugin_name in failed_entry_points:
                raise PluginError(
                    f"Plugin '{plugin_name}' failed to load via its entry point. "
                    f"Original error: {failed_entry_points[plugin_name]}"
                ) from failed_entry_points[plugin_name]
            else:
                raise PluginError(
                    f"Plugin '{plugin_name}' not found. "
                    "Ensure it is installed and declares a 'platzky.plugins' entry point."
                )

        except PluginError:
            raise
        except ValidationError as e:
            raise PluginError(f"Invalid config for plugin {plugin_name}: {e}") from e
        except Exception as e:
            logger.exception("Error processing plugin %s", plugin_name)
            raise PluginError(f"Error processing plugin {plugin_name}: {e}") from e

    return app
