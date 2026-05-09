"""Plugin discovery, loading, and lifecycle management."""

from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import logging
import os
from types import ModuleType
from typing import TYPE_CHECKING, Any, Optional, Type

import deprecation

from platzky.plugin.plugin import (
    CmsModuleBase,
    ContentFilterBase,
    LoginBase,
    NotifierBase,
    PluginBase,
    PluginError,
)

if TYPE_CHECKING:
    from platzky.engine import Engine

logger = logging.getLogger(__name__)

_CAPABILITY_BASES: tuple[type, ...] = (NotifierBase, LoginBase, CmsModuleBase, ContentFilterBase)

_ENTRY_POINT_GROUP = "platzky.plugins"


def discover_plugins() -> dict[str, type[PluginBase[Any]]]:
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
    discovered: dict[str, type[PluginBase[Any]]] = {}
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


def _is_class_plugin(plugin_module: ModuleType) -> Optional[Type[PluginBase[Any]]]:
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


def _is_safe_locale_dir(locale_dir: str, plugin_instance: PluginBase[Any]) -> bool:
    """Validate that a locale directory is safe to use.

    Prevents malicious plugins from exposing arbitrary filesystem paths
    by ensuring the locale directory is within the plugin's module directory.

    Args:
        locale_dir: Path to the locale directory
        plugin_instance: The plugin instance

    Returns:
        True if the locale directory is safe to use, False otherwise
    """
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


def _register_plugin_locale(
    app: Engine, plugin_instance: PluginBase[Any], plugin_name: str
) -> None:
    """Register plugin's locale directory with Babel if it exists.

    Args:
        app: The Platzky Engine instance
        plugin_instance: The plugin instance
        plugin_name: Name of the plugin for logging
    """
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

    babel_config = app.extensions.get("babel")
    if babel_config and locale_dir not in babel_config.translation_directories:
        babel_config.translation_directories.append(locale_dir)
        logger.info("Registered locale directory for plugin %s: %s", plugin_name, locale_dir)


def _register_plugin_capabilities(app: Engine, instance: PluginBase[Any], plugin_name: str) -> None:
    """Register a plugin instance under all matching capability keys.

    Each recognised capability base class becomes a key in app.plugins so the
    engine can look up e.g. all NotifierBase plugins without knowing concrete
    types.  Plugins that don't match any capability are stored under PluginBase
    so they are still discoverable.

    Args:
        app: The Platzky Engine instance
        instance: The instantiated plugin
        plugin_name: Name of the plugin for logging
    """
    registered = False
    for base in _CAPABILITY_BASES:
        if isinstance(instance, base):
            app.plugins[base].append(instance)
            registered = True
            logger.debug("Registered plugin '%s' under capability %s", plugin_name, base.__name__)

    # Also store under the concrete type so callers can look up plugins by their
    # exact class (e.g. engine.get_plugins(SimpleNotifier)).  This double-registration
    # is intentional: the capability-base key supports duck-typed dispatch, while
    # the concrete-type key supports precise lookups in tests and introspection.
    app.plugins[type(instance)].append(instance)

    if not registered:
        app.plugins[PluginBase].append(instance)


def _load_class_plugin(
    app: Engine,
    plugin_class: type[PluginBase[Any]],
    plugin_config: dict[str, Any],
    plugin_name: str,
) -> Engine:
    """Instantiate and register a class-based plugin."""
    plugin_instance = plugin_class(plugin_config)
    app.loaded_plugins.append(plugin_instance)
    # MRO-based identity check: every class inherits process() from PluginBase so
    # hasattr() would always return True.  Comparing unbound method objects via `is`
    # detects a genuine override without invoking the deprecation warning that calling
    # the base no-op implementation would raise.
    if type(plugin_instance).process is not PluginBase.process:
        app = plugin_instance.process(app)
    # Register locale and capabilities on the (possibly replaced) app returned by process().
    _register_plugin_locale(app, plugin_instance, plugin_name)
    _register_plugin_capabilities(app, plugin_instance, plugin_name)
    logger.info("Processed class-based plugin: %s", plugin_name)
    return app


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

        try:
            if plugin_name in discovered:
                app = _load_class_plugin(app, discovered[plugin_name], plugin_config, plugin_name)
            else:
                # Fallback: deprecated module-scanning approach
                logger.warning(
                    "Plugin '%s' has no 'platzky.plugins' entry point. "
                    "Falling back to module-name convention — this is deprecated and will be "
                    "removed in 2.0.0. Add an entry point to your plugin package.",
                    plugin_name,
                )
                plugin_module = find_plugin(plugin_name)
                plugin_class = _is_class_plugin(plugin_module)

                if plugin_class:
                    app = _load_class_plugin(app, plugin_class, plugin_config, plugin_name)
                elif hasattr(plugin_module, "process"):
                    app = _process_legacy_plugin(plugin_module, app, plugin_config, plugin_name)
                else:
                    raise PluginError(
                        f"Plugin {plugin_name} doesn't implement either the PluginBase interface "
                        f"or provide a process() function"
                    )

        except PluginError:
            raise
        except Exception as e:
            logger.exception("Error processing plugin %s", plugin_name)
            raise PluginError(f"Error processing plugin {plugin_name}: {e}") from e

    return app
