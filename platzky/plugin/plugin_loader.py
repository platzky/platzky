"""Plugin discovery, loading, and lifecycle management."""

from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import logging
from types import ModuleType
from typing import TYPE_CHECKING, Any, Optional, Type

import deprecation

from platzky.content_types import ContentType
from platzky.notification_topics import NotificationTopic
from platzky.plugin.plugin import PluginBase, PluginError

if TYPE_CHECKING:
    from platzky.engine import Engine

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "platzky.plugins"


def discover_plugins() -> dict[str, type[PluginBase]]:
    """Return all installed platzky plugins declared via entry points.

    Plugin packages advertise themselves by declaring a ``platzky.plugins``
    entry point in their package metadata, e.g. in ``pyproject.toml``::

        [tool.poetry.plugins."platzky.plugins"]
        sendmail = "platzky_sendmail.entrypoint:SendMailPlugin"

    Only plugins installed in the current environment are returned.
    Configured (active) plugins are a subset determined by the database.

    Returns:
        Mapping of plugin name to plugin class for every installed plugin.
    """
    discovered: dict[str, type[PluginBase]] = {}
    for ep in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP):
        try:
            plugin_class = ep.load()
        except Exception:
            logger.exception("Failed to load entry point '%s'", ep.name)
            continue

        if not (inspect.isclass(plugin_class) and issubclass(plugin_class, PluginBase)):
            logger.warning(
                "Entry point '%s' does not point to a PluginBase subclass, skipping",
                ep.name,
            )
            continue

        if ep.name in discovered:
            raise ValueError(
                f"Duplicate plugin entry-point name '{ep.name}': "
                f"already registered as {discovered[ep.name]}, "
                f"conflicting class {plugin_class}"
            )
        discovered[ep.name] = plugin_class
        logger.debug("Discovered plugin '%s' via entry points", ep.name)

    return discovered


@deprecation.deprecated(
    deprecated_in="1.5.0",
    removed_in="2.0.0",
    details=(
        "Importing plugins by module name is deprecated. "
        "Declare a 'platzky.plugins' entry point in your plugin package instead."
    ),
)
def find_plugin(plugin_name: str) -> ModuleType:
    """Find plugin by name and return it as module.

    Deprecated: declare a ``platzky.plugins`` entry point in the plugin package
    so it is discoverable via :func:`discover_plugins`.

    Args:
        plugin_name: name of plugin to find

    Raises:
        PluginError: if plugin cannot be imported

    Returns:
        module of plugin
    """
    try:
        return importlib.import_module(f"platzky_{plugin_name}")
    except ImportError as e:
        raise PluginError(
            f"Plugin {plugin_name} not found. Ensure it's installed and follows "
            f"the 'platzky_<plugin_name>' naming convention"
        ) from e


def _is_class_plugin(plugin_module: ModuleType) -> Optional[Type[PluginBase]]:
    """Check if the plugin module contains a PluginBase implementation."""
    for _, obj in inspect.getmembers(plugin_module):
        if inspect.isclass(obj) and issubclass(obj, PluginBase) and obj != PluginBase:
            return obj
    return None


@deprecation.deprecated(
    deprecated_in="1.2.0",
    removed_in="2.0.0",
    details=(
        "Legacy plugin style using the entrypoint process() function is deprecated. "
        "Migrate to PluginBase to support plugin translations and other features. "
        "See: https://platzky.readthedocs.io/en/latest/plugins.html"
    ),
)
def _process_legacy_plugin(
    plugin_module: ModuleType, app: Engine, plugin_config: dict[str, Any], plugin_name: str
) -> Engine:
    """Process a legacy plugin using the entrypoint approach.

    DEPRECATED: This function will be removed in version 2.0.0.
    Please migrate your plugin to extend PluginBase.

    Args:
        plugin_module: The plugin module
        app: The Platzky Engine instance
        plugin_config: Plugin configuration dictionary
        plugin_name: Name of the plugin

    Returns:
        Platzky Engine with processed plugin
    """
    app = plugin_module.process(app, plugin_config)
    logger.warning(
        "Plugin '%s' uses deprecated legacy interface. "
        "This will be removed in version 2.0.0. "
        "Migrate to PluginBase: https://platzky.readthedocs.io/",
        plugin_name,
    )
    return app


def _load_legacy_plugin(
    app: Engine,
    plugin_name: str,
    plugin_config: dict[str, Any],
    allowed_topics: frozenset[NotificationTopic] | None,
    allowed_content_types: frozenset[ContentType] | None,
) -> Engine:
    """Load a plugin using the deprecated module-name fallback convention."""
    logger.warning(
        "Plugin '%s' has no 'platzky.plugins' entry point. "
        "Falling back to module-name convention — this is deprecated and will be "
        "removed in 2.0.0. Add an entry point to your plugin package.",
        plugin_name,
    )
    plugin_module = find_plugin(plugin_name)
    plugin_class = _is_class_plugin(plugin_module)

    if plugin_class:
        return app.load_plugin(
            plugin_class, plugin_config, plugin_name, allowed_topics, allowed_content_types
        )
    if hasattr(plugin_module, "process"):
        return _process_legacy_plugin(plugin_module, app, plugin_config, plugin_name)
    raise PluginError(
        f"Plugin {plugin_name} doesn't implement either the PluginBase interface "
        f"or provide a process() function"
    )


def plugify(app: Engine) -> Engine:
    """Load and initialise plugins configured in the database.

    Plugins are looked up via ``platzky.plugins`` entry points first.
    If a configured plugin has no entry point, the legacy module-name
    convention (``platzky_<name>``) is used as a fallback — this fallback
    is deprecated and will be removed in 2.0.0.

    Args:
        app: Platzky Engine instance

    Returns:
        Platzky Engine with all configured plugins loaded

    Raises:
        PluginError: if a configured plugin cannot be loaded or initialised
    """
    plugins_data = app.db.get_plugins_data()
    discovered = discover_plugins()

    for plugin_data in plugins_data:
        plugin_config = plugin_data["config"]
        plugin_name = plugin_data["name"]
        raw_allowed = plugin_data.get("allowed_topics")
        allowed_topics: frozenset[NotificationTopic] | None = (
            frozenset(raw_allowed) if raw_allowed is not None else None
        )
        raw_allowed_ct = plugin_data.get("allowed_content_types")
        allowed_content_types: frozenset[ContentType] | None = (
            frozenset(raw_allowed_ct) if raw_allowed_ct is not None else None
        )

        try:
            if plugin_name in discovered:
                app = app.load_plugin(
                    discovered[plugin_name],
                    plugin_config,
                    plugin_name,
                    allowed_topics,
                    allowed_content_types,
                )
            else:
                app = _load_legacy_plugin(
                    app, plugin_name, plugin_config, allowed_topics, allowed_content_types
                )

        except PluginError:
            raise
        except Exception as e:
            logger.exception("Error processing plugin %s", plugin_name)
            raise PluginError(f"Error processing plugin {plugin_name}: {e}") from e

    return app
