"""Sphinx extension for auto-documenting plugin capability base classes.

Provides the ``plugin-capabilities`` directive that generates a summary table
and import block from ``platzky.plugin.CAPABILITY_BASES``.  Adding a new
capability base class to that tuple is sufficient — the docs update at the
next build with no manual edits required.

Usage in RST::

    .. plugin-capabilities::

"""

from __future__ import annotations

import inspect

from docutils import nodes
from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective
from sphinx.util.logging import getLogger

logger = getLogger(__name__)


def _first_sentence(docstring: str | None) -> str:
    """Return the first sentence of a docstring, or an empty string."""
    if not docstring:
        return ""
    text = inspect.cleandoc(docstring)
    sentence = text.split(".")[0].replace("\n", " ").strip()
    return sentence + "." if sentence else ""


def _build_rst(capability_bases: tuple[type, ...]) -> list[str]:
    """Build RST lines for the capability table and import block."""
    lines: list[str] = []

    # Summary table
    lines += [
        ".. list-table::",
        "   :header-rows: 1",
        "   :widths: 40 60",
        "",
        "   * - Base class",
        "     - When to use",
    ]
    for cls in capability_bases:
        lines += [
            f"   * - :class:`~{cls.__module__}.{cls.__name__}`",
            f"     - {_first_sentence(cls.__doc__)}",
        ]
    lines.append("")

    # Import block
    imports = ", ".join(c.__name__ for c in capability_bases)
    lines += [
        "All capability classes (plus :class:`~platzky.plugin.plugin.PluginBase` itself)"
        " are importable directly from ``platzky``::",
        "",
        f"    from platzky import PluginBase, {imports}",
        "",
    ]

    return lines


class PluginCapabilitiesDirective(SphinxDirective):
    """Directive to auto-generate plugin capability documentation."""

    has_content = False
    required_arguments = 0
    optional_arguments = 0

    def run(self) -> list[nodes.Node]:
        """Generate plugin capability documentation nodes."""
        try:
            from platzky.plugin import CAPABILITY_BASES
        except ImportError as e:
            logger.warning(
                "Could not import CAPABILITY_BASES: %s. "
                "Plugin capability documentation will not be generated.",
                e,
            )
            warning = nodes.warning()
            warning += nodes.paragraph(
                text="Plugin capability documentation could not be generated. "
                "See build logs for details."
            )
            return [warning]

        rst_lines = _build_rst(CAPABILITY_BASES)
        node = nodes.container()
        self.state.nested_parse(StringList(rst_lines), self.content_offset, node)
        return [node]


def setup(app: Sphinx) -> dict[str, object]:
    """Register the plugin-capabilities directive with Sphinx."""
    app.add_directive("plugin-capabilities", PluginCapabilitiesDirective)
    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
