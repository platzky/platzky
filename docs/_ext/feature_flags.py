"""Sphinx extension for auto-documenting feature flags.

This extension provides the ``feature-flags`` directive that automatically
generates documentation for all built-in ``FeatureFlag`` instances.

Usage in RST:

    .. feature-flags::

This will generate a formatted list of all available feature flags with their
descriptions, types, defaults, and YAML examples.
"""

from __future__ import annotations

from _shared import generated_reference_run, register_directive
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective


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


def _build_all_flags_rst() -> list[str]:
    """Import the built-in flags and build RST lines documenting all of them."""
    from platzky.feature_flags import BUILTIN_FLAGS

    rst_lines: list[str] = []
    for flag in sorted(BUILTIN_FLAGS, key=lambda f: f.alias):
        rst_lines.extend(_build_flag_rst(flag))
    return rst_lines


class FeatureFlagsDirective(SphinxDirective):
    """Directive to auto-generate feature flags documentation."""

    has_content = False
    required_arguments = 0
    optional_arguments = 0
    run = generated_reference_run(_build_all_flags_rst, "Feature flags")


def setup(app: Sphinx) -> dict[str, object]:
    """Register the feature-flags directive with Sphinx."""
    return register_directive(app, "feature-flags", FeatureFlagsDirective)
