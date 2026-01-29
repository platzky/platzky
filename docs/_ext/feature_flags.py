"""Sphinx extension for auto-documenting feature flags.

This extension provides the ``feature-flags`` directive that automatically
generates documentation for all feature flags defined in FeatureFlagsConfig.

Usage in RST:

    .. feature-flags::

This will generate a formatted list of all available feature flags with their
descriptions, types, defaults, and YAML examples.
"""

from docutils import nodes
from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective
from sphinx.util.logging import getLogger

logger = getLogger(__name__)


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
                f"Could not import FeatureFlagsConfig: {e}. "
                "Feature flags documentation will not be generated. "
                "Ensure platzky is installed in the documentation build environment."
            )
            # Return a warning paragraph instead of failing
            warning = nodes.warning()
            warning += nodes.paragraph(
                text="Feature flags documentation could not be generated. "
                "See build logs for details."
            )
            return [warning]

        # Build RST content
        rst_lines: list[str] = []

        for field_name, field_info in FeatureFlagsConfig.model_fields.items():
            # Use alias if defined, otherwise use field name as-is (don't uppercase)
            config_key = field_info.alias if field_info.alias else field_name
            description = field_info.description or "No description available."
            default = field_info.default

            # Derive type from annotation for future-proofing
            type_annotation = field_info.annotation
            if type_annotation is bool:
                type_str = "bool"
            elif type_annotation is not None:
                type_str = getattr(type_annotation, "__name__", str(type_annotation))
            else:
                type_str = "Any"

            # Format default value for display
            if isinstance(default, bool):
                default_str = "true" if default else "false"
            else:
                default_str = str(default)

            # Generate RST for this flag
            rst_lines.append(f"**{config_key}**")
            rst_lines.append("")
            rst_lines.append(f":Type: ``{type_str}``")
            rst_lines.append(f":Default: ``{default_str}``")
            rst_lines.append(f":Field name: ``{field_name}``")
            rst_lines.append("")
            rst_lines.append(description)
            rst_lines.append("")

            # Add warning for dangerous flags
            if "never" in description.lower() and "production" in description.lower():
                rst_lines.append(".. warning::")
                rst_lines.append(f"   Never enable {config_key} in production.")
                rst_lines.append("")

            # Add YAML example
            rst_lines.append(".. code-block:: yaml")
            rst_lines.append("")
            rst_lines.append("    FEATURE_FLAGS:")
            rst_lines.append(f"      {config_key}: {default_str}")
            rst_lines.append("")

        # Parse RST content into nodes
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
