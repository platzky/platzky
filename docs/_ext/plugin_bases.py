"""Sphinx extension for auto-documenting plugin base classes.

Provides the ``plugin-bases`` directive that generates a summary table
and import block from ``platzky.plugin.PLUGIN_BASES``.  Adding a new
base class to that tuple is sufficient — the docs update at the
next build with no manual edits required.

Usage in RST::

    .. plugin-bases::

"""

import inspect

from _shared import generated_reference_run, register_directive
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


def _build_all_bases_rst() -> list[str]:
    """Import the plugin base classes and build RST lines documenting all of them."""
    from platzky.plugin import PLUGIN_BASES

    return _build_rst(PLUGIN_BASES)


class PluginBasesDirective(SphinxDirective):
    """Directive to auto-generate plugin base class documentation."""

    has_content = False
    required_arguments = 0
    optional_arguments = 0
    run = generated_reference_run(_build_all_bases_rst, "Plugin base classes")


def setup(app: Sphinx) -> dict[str, object]:
    """Register the plugin-bases directive with Sphinx."""
    return register_directive(app, "plugin-bases", PluginBasesDirective)
