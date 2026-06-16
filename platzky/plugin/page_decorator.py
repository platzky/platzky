"""PageDecoratorPluginBase capability — plugins that inject HTML into page sections."""

from abc import ABC

from platzky.page_sections import PageSection
from platzky.plugin.plugin import PluginBase


class PageDecoratorPluginBase(PluginBase, ABC):
    """Base class for page-decorator plugins.

    Subclasses declare which page sections they produce content for via
    ``accepted_page_sections``. The engine injects only the intersection of that
    set and what the admin permits in the plugin config — neither side alone
    controls injection.

    ``get_head_html`` / ``get_body_html`` are called once at app startup; use the
    plugin's own config for environment-specific values (for example public IDs or
    feature flags). Never embed secrets/credentials in injected HTML.

    Override ``get_head_html`` to inject HTML into ``<head>``.
    Override ``get_body_html`` to inject HTML at the start of ``<body>``.
    """

    accepted_page_sections: frozenset[PageSection] = frozenset()

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
