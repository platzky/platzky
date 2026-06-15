"""Plugin discovery, loading, and lifecycle management."""

from __future__ import annotations

import importlib.metadata
import inspect
import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from platzky.content_types import ContentType
from platzky.notification_topics import NotificationTopic
from platzky.page_sections import PageSection
from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.plugin.notifier import NotifierPluginBase
from platzky.plugin.page_decorator import PageDecoratorPluginBase
from platzky.plugin.plugin import PluginBase, PluginError
from platzky.plugin.plugin_config import (
    ContentTransformerPluginConfig,
    NotifyPluginConfig,
    PageDecoratorPluginConfig,
    PluginConfigBase,
)

if TYPE_CHECKING:
    from platzky.engine import Engine

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "platzky.plugins"


def _extract_allowlists(
    pc: PluginConfigBase, plugin_class: type
) -> tuple[frozenset[NotificationTopic], frozenset[ContentType], frozenset[PageSection]]:
    raw = pc.model_dump()
    allowed_topics = (
        NotifyPluginConfig.model_validate(raw).allowed_topics
        if issubclass(plugin_class, NotifierPluginBase)
        else frozenset()
    )
    allowed_content_types = (
        ContentTransformerPluginConfig.model_validate(raw).allowed_content_types
        if issubclass(plugin_class, ContentTransformerPluginBase)
        else frozenset()
    )
    allowed_page_sections = (
        PageDecoratorPluginConfig.model_validate(raw).allowed_page_sections
        if issubclass(plugin_class, PageDecoratorPluginBase)
        else frozenset()
    )
    return allowed_topics, allowed_content_types, allowed_page_sections


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
    discovered, _ = _discover_entry_points()
    return discovered


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

    for pc in plugins_data:
        try:
            if pc.name in discovered:
                plugin_class = discovered[pc.name]
                allowed_topics, allowed_content_types, allowed_page_sections = _extract_allowlists(
                    pc, plugin_class
                )
                app = app.load_plugin(
                    plugin_class,
                    pc.config,
                    pc.name,
                    allowed_topics,
                    allowed_content_types,
                    allowed_page_sections,
                )
            elif pc.name in failed_entry_points:
                raise PluginError(
                    f"Plugin '{pc.name}' failed to load via its entry point. "
                    f"Original error: {failed_entry_points[pc.name]}"
                ) from failed_entry_points[pc.name]
            else:
                raise PluginError(
                    f"Plugin '{pc.name}' not found. "
                    "Ensure it is installed and declares a 'platzky.plugins' entry point."
                )

        except PluginError:
            raise
        except ValidationError as e:
            raise PluginError(f"Invalid config for plugin {pc.name}: {e}") from e
        except Exception as e:
            logger.exception("Error processing plugin %s", pc.name)
            raise PluginError(f"Error processing plugin {pc.name}: {e}") from e

    return app
