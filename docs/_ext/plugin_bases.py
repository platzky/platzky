"""Sphinx extension for auto-documenting plugin base classes.

Provides the ``plugin-bases`` directive that generates a summary table
and import block from ``platzky.plugin.PLUGIN_BASES``.  Adding a new
base class to that tuple is sufficient — the docs update at the
next build with no manual edits required.

Usage in RST::

    .. plugin-bases::

"""

import inspect

from docutils import nodes
from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective


def _first_sentence(docstring: str | None) -> str:
    """Return the first sentence of a docstring, or an empty string."""
    if not docstring:
        return ""
    text = inspect.cleandoc(docstring)
    sentence = text.split(".")[0].replace("\n", " ").strip()
    return sentence + "." if sentence else ""


def _build_rst(plugin_bases: tuple[type, ...]) -> list[str]:
    """Build RST lines for the plugin bases table and import block."""
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
    for cls in plugin_bases:
        lines += [
            f"   * - :class:`~{cls.__module__}.{cls.__name__}`",
            f"     - {_first_sentence(cls.__doc__)}",
        ]
    lines.append("")

    # Import block
    imports = ", ".join(cls.__name__ for cls in plugin_bases)
    lines += [
        "All plugin base classes (plus :class:`~platzky.plugin.plugin.PluginBase` itself)"
        " are importable directly from ``platzky``::",
        "",
        f"    from platzky import PluginBase, {imports}",
        "",
    ]

    return lines


class PluginBasesDirective(SphinxDirective):
    """Directive to auto-generate plugin base class documentation."""

    has_content = False
    required_arguments = 0
    optional_arguments = 0

    def run(self) -> list[nodes.Node]:
        """Generate plugin base class documentation nodes."""
        from platzky.plugin import PLUGIN_BASES

        rst_lines = _build_rst(PLUGIN_BASES)
        node = nodes.container()
        self.state.nested_parse(StringList(rst_lines), self.content_offset, node)
        return [node]


def setup(app: Sphinx) -> dict[str, object]:
    """Register the plugin-bases directive with Sphinx."""
    app.add_directive("plugin-bases", PluginBasesDirective)
    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
