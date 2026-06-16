"""PageDecoratorPluginBase capability — plugins that inject HTML into page sections."""

import logging
from abc import ABC

from platzky.page_sections import PageSection
from platzky.plugin.plugin import PluginBase

logger = logging.getLogger(__name__)


class PageDecoratorPluginBase(PluginBase, ABC):
    """Base class for page-decorator plugins.

    Subclasses declare which page sections they produce content for via
    ``accepted_page_sections``. The engine injects only the intersection of that
    set and what the admin permits in the plugin config — neither side alone
    controls injection.

    ``get_head_html`` / ``get_body_html`` are called once at app startup; use the
    plugin's own config for environment-specific values (API keys, feature flags).

    Override ``get_head_html`` to inject HTML into ``<head>``.
    Override ``get_body_html`` to inject HTML at the start of ``<body>``.
    """

    accepted_page_sections: frozenset[PageSection] = frozenset()

    def _warn_if_no_capabilities(self, plugin_name: str) -> None:
        """Log if accepted_page_sections is empty, then delegate to super()."""
        super()._warn_if_no_capabilities(plugin_name)
        if not self.accepted_page_sections:
            logger.debug(
                "Plugin %s declares no accepted_page_sections; nothing will be injected.",
                plugin_name,
            )

    def get_head_html(self) -> str:
        """Return HTML to inject into the page ``<head>``.

        Returns:
            HTML string; empty string by default.
        """
        return ""

    def get_body_html(self) -> str:
        """Return HTML to inject at the start of the page ``<body>``.

        Returns:
            HTML string; empty string by default.
        """
        return ""
