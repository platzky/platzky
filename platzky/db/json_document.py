"""Shared helper for reading the JSON-family document's site_content section.

Used by `JsonBlogStorage`, `JsonSiteConfigRepository`, and `Json.health_check`
-- three independent call sites needing the same "read site_content, raise if
missing" logic.
"""

from typing import Any

from platzky.db.exceptions import DBError


def get_site_content(data: dict[str, Any]) -> dict[str, Any]:
    """Return the site_content section of a loaded document.

    Args:
        data: The loaded document.

    Returns:
        The site_content section.

    Raises:
        DBError: If site_content is missing from the document.
    """
    content = data.get("site_content")
    if content is None:
        raise DBError("site_content section is missing from database")
    return content
