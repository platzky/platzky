"""Sphinx extension for auto-documenting built-in shortcodes.

Provides the ``shortcode-reference`` directive that generates a signature,
description, attribute table, and example for every shortcode registered in
``platzky.shortcodes.builtins.get_builtin_shortcodes``. Adding, removing, or
changing the attributes of a built-in shortcode updates the docs at the next
build with no manual edits required.

Usage in RST::

    .. shortcode-reference::

"""

from __future__ import annotations

from _shared import generated_reference_run, register_directive
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective


def _signature(shortcode: object) -> str:
    """Build the bracket syntax for a shortcode, e.g. ``[image url="…"]``.

    Args:
        shortcode: A registered ``Shortcode`` instance.

    Returns:
        The tag written as an author would write it, with a placeholder value
        for each declared attribute.
    """
    name = shortcode.name  # type: ignore[attr-defined]
    attrs = " ".join(f'{attr.name}="…"' for attr in shortcode.attributes)  # type: ignore[attr-defined]
    opening = f"[{name} {attrs}]" if attrs else f"[{name}]"
    if shortcode.kind == "void":  # type: ignore[attr-defined]
        return opening
    return f"{opening}…[/{name}]"


def _attribute_table_rst(shortcode: object) -> list[str]:
    """Build the RST table of a shortcode's attributes.

    Args:
        shortcode: A registered ``Shortcode`` instance.

    Returns:
        RST lines for the table: one row per declared attribute, naming its default and
        what it accepts. Nothing at all when the shortcode declares no attributes.
    """
    attrs = list(shortcode.attributes)  # type: ignore[attr-defined]
    if not attrs:
        return []

    lines = [
        "    .. list-table::",
        "       :header-rows: 1",
        "       :widths: 20 20 60",
        "",
        "       * - Attribute",
        "         - Default",
        "         - Description",
    ]
    for attr in attrs:
        default = f"``{attr.default}``" if attr.default else "—"
        rule = str(attr.constraints)
        accepts = f" Must be {rule}; anything else renders nothing." if rule else ""
        lines += [
            f"       * - ``{attr.name}``",
            f"         - {default}",
            f"         - {attr.description}{accepts}",
        ]
    lines.append("")
    return lines


def _build_shortcode_rst(shortcode: object) -> list[str]:
    """Build RST lines documenting a single shortcode.

    Args:
        shortcode: A registered ``Shortcode`` instance.

    Returns:
        RST lines: signature, description, attribute table, and example.
    """
    lines = [
        f"``{_signature(shortcode)}``",
        f"    {shortcode.description}",  # type: ignore[attr-defined]
        "",
    ]

    lines += _attribute_table_rst(shortcode)

    example = shortcode.example  # type: ignore[attr-defined]
    if example and "\n" in example:
        lines += ["    Example::", ""]
        lines += [f"        {line}" for line in example.splitlines()]
        lines.append("")
    elif example:
        lines += [f"    Example: ``{example}``", ""]

    notes = shortcode.notes  # type: ignore[attr-defined]
    if notes:
        lines += [f"    {notes}", ""]

    return lines


def _build_all_shortcodes_rst() -> list[str]:
    """Import the built-in shortcodes and build RST lines documenting all of them."""
    from platzky.shortcodes.builtins import get_builtin_shortcodes

    rst_lines: list[str] = []
    for shortcode in get_builtin_shortcodes().values():
        rst_lines.extend(_build_shortcode_rst(shortcode))
    return rst_lines


class ShortcodeReferenceDirective(SphinxDirective):
    """Directive to auto-generate built-in shortcode documentation."""

    has_content = False
    required_arguments = 0
    optional_arguments = 0
    run = generated_reference_run(_build_all_shortcodes_rst, "Built-in shortcode")


def setup(app: Sphinx) -> dict[str, object]:
    """Register the shortcode-reference directive with Sphinx."""
    return register_directive(app, "shortcode-reference", ShortcodeReferenceDirective)
