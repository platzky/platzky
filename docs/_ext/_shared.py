"""Shared scaffolding for this directory's doc-generation Sphinx extensions.

``feature_flags``, ``plugin_bases``, and ``shortcodes`` each register one directive
that imports some live platzky object, builds RST lines describing it, and parses
those lines into the page. This module holds the boilerplate common to all three:
turning RST lines into nodes, guarding the platzky import so a docs build without
platzky installed gets a warning instead of a crash, and registering the directive.
"""

from __future__ import annotations

from collections.abc import Callable

from docutils import nodes
from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective
from sphinx.util.logging import getLogger

logger = getLogger(__name__)


def generated_reference_run(
    build_lines: Callable[[], list[str]], what: str
) -> Callable[[SphinxDirective], list[nodes.Node]]:
    """Build a directive ``run`` method that renders RST lines from live platzky objects.

    Args:
        build_lines: Zero-argument callable producing the RST lines to render. Should
            do its own ``from platzky... import ...`` internally, so an ``ImportError``
            it raises is caught here rather than at module load time.
        what: Human-readable name of what is being generated, used in the message shown
            when ``build_lines`` fails to import what it needs.

    Returns:
        A function usable as a ``SphinxDirective`` subclass's ``run`` method.
    """

    def run(self: SphinxDirective) -> list[nodes.Node]:
        try:
            lines = build_lines()
        except ImportError as e:
            logger.warning(
                "Could not import %s: %s. %s documentation will not be generated. "
                "Ensure platzky is installed in the documentation build environment.",
                what,
                e,
                what,
            )
            warning = nodes.warning()
            warning += nodes.paragraph(
                text=f"{what} documentation could not be generated. " "See build logs for details."
            )
            return [warning]

        node = nodes.container()
        self.state.nested_parse(StringList(lines), self.content_offset, node)
        return [node]

    return run


def register_directive(
    app: Sphinx, name: str, directive: type[SphinxDirective]
) -> dict[str, object]:
    """Register a directive and return the standard extension ``setup()`` metadata.

    Args:
        app: The running Sphinx application.
        name: The directive's name as written in RST, e.g. ``"feature-flags"``.
        directive: The ``SphinxDirective`` subclass to register under that name.

    Returns:
        The metadata dict Sphinx expects an extension's ``setup()`` to return.
    """
    app.add_directive(name, directive)
    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
