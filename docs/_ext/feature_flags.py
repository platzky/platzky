"""Sphinx extension for auto-documenting feature flags.

This extension provides the ``feature-flags`` directive that automatically
generates documentation for all registered ``FeatureFlag`` instances.

Usage in RST:

    .. feature-flags::

This will generate a formatted list of all available feature flags with their
descriptions, types, defaults, and YAML examples.
"""

from __future__ import annotations

from docutils import nodes
from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective
from sphinx.util.logging import getLogger

logger = getLogger(__name__)


def _default_display_value(default: bool) -> str:
    """Return a YAML-friendly display string for a default value."""
    return "true" if default else "false"


def _build_flag_rst(flag: object) -> list[str]:
    """Build RST lines documenting a single feature flag."""
    alias = getattr(flag, "alias", repr(flag))
    description = getattr(flag, "description", "") or "No description available."
    default = getattr(flag, "default", False)
    default_str = _default_display_value(default)

    lines = [
        f"**{alias}**",
        "",
        ":Type: ``bool``",
        f":Default: ``{default_str}``",
        "",
        description,
        "",
    ]

    if getattr(flag, "production_warning", False):
        lines.extend(
            [
                ".. warning::",
                f"   Never enable {alias} in production.",
                "",
            ]
        )

    lines.extend(
        [
            ".. code-block:: yaml",
            "",
            "    FEATURE_FLAGS:",
            f"      {alias}: {default_str}",
            "",
        ]
    )

    return lines


class FeatureFlagsDirective(SphinxDirective):
    """Directive to auto-generate feature flags documentation."""

    has_content = False
    required_arguments = 0
    optional_arguments = 0

    def run(self) -> list[nodes.Node]:
        """Generate feature flags documentation nodes."""
        try:
            from platzky.feature_flags import all_flags
        except ImportError as e:
            logger.warning(
                "Could not import all_flags: %s. "
                "Feature flags documentation will not be generated. "
                "Ensure platzky is installed in the documentation build environment.",
                e,
            )
            warning = nodes.warning()
            warning += nodes.paragraph(
                text="Feature flags documentation could not be generated. "
                "See build logs for details."
            )
            return [warning]

        rst_lines: list[str] = []
        for flag in all_flags():
            rst_lines.extend(_build_flag_rst(flag))

        node = nodes.container()
        self.state.nested_parse(
            StringList(rst_lines),
            self.content_offset,
            node,
        )

        return [node]


def setup(app: Sphinx) -> dict[str, object]:
    """Register the feature-flags directive with Sphinx."""
    app.add_directive("feature-flags", FeatureFlagsDirective)

    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
