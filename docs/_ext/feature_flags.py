"""Sphinx extension for auto-documenting feature flags.

This extension provides the ``feature-flags`` directive that automatically
generates documentation for all feature flags defined in FeatureFlagsConfig.

Usage in RST:

    .. feature-flags::

This will generate a formatted list of all available feature flags with their
descriptions, types, defaults, and YAML examples.
"""

from __future__ import annotations

from docutils import nodes
from docutils.statemachine import StringList
from pydantic.fields import FieldInfo
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective
from sphinx.util.logging import getLogger

logger = getLogger(__name__)


def _type_display_name(annotation: type[object] | None) -> str:
    """Return a human-readable type name for a field annotation."""
    if annotation is bool:
        return "bool"
    if annotation is not None:
        return getattr(annotation, "__name__", str(annotation))
    return "Any"


def _default_display_value(default: object) -> str:
    """Return a YAML-friendly display string for a default value."""
    if isinstance(default, bool):
        return "true" if default else "false"
    return str(default)


def _build_flag_rst(field_name: str, field_info: FieldInfo) -> list[str]:
    """Build RST lines documenting a single feature flag."""
    config_key = field_info.alias if field_info.alias else field_name
    description = field_info.description or "No description available."
    type_str = _type_display_name(field_info.annotation)
    default_str = _default_display_value(field_info.default)

    lines = [
        f"**{config_key}**",
        "",
        f":Type: ``{type_str}``",
        f":Default: ``{default_str}``",
        f":Field name: ``{field_name}``",
        "",
        description,
        "",
    ]

    if "never" in description.lower() and "production" in description.lower():
        lines.extend(
            [
                ".. warning::",
                f"   Never enable {config_key} in production.",
                "",
            ]
        )

    lines.extend(
        [
            ".. code-block:: yaml",
            "",
            "    FEATURE_FLAGS:",
            f"      {config_key}: {default_str}",
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
            from platzky.config import FeatureFlagsConfig
        except ImportError as e:
            logger.warning(
                "Could not import FeatureFlagsConfig: %s. "
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
        for field_name, field_info in FeatureFlagsConfig.model_fields.items():
            rst_lines.extend(_build_flag_rst(field_name, field_info))

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
