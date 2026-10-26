"""The JSON-family document shared by every JSON repository.

`JsonDocument` loads the document once and holds it together with its store and
write lock. `Json` builds one and hands the same instance to
`JsonBlogStorage`, `JsonSiteConfigRepository` and `JsonPluginConfigRepository`,
so they all operate on the exact same in-memory dict --
`FileStore.load()` re-reads and re-parses the file on every call rather than
returning a memoized object, so each repository loading independently would
see its own copy. The dict is only ever mutated in place, never reassigned.

A repository that writes must hold `document.write_lock` and persist with
`document.store.save(document.data)`.

`get_site_content` is the shared "read site_content, raise if missing" helper
used by those repositories and `Json.health_check`.
"""

import threading
from typing import Any

from platzky.db.exceptions import DBError
from platzky.db.json_stores import JsonStore


class JsonDocument:
    """A loaded JSON document with its store and write lock."""

    def __init__(self, store: JsonStore) -> None:
        """Load the document from the store, once.

        Args:
            store: Storage transport to load the document from and persist
                writes to.
        """
        self.store: JsonStore = store
        self.data: dict[str, Any] = store.load()
        self.write_lock = threading.Lock()


def get_site_content(data: dict[str, Any]) -> dict[str, Any]:
    """Return the site_content section of a loaded document.

    Args:
        data: The loaded document.

    Returns:
        The site_content section.

    Raises:
        DBError: If site_content is missing or not an object.
    """
    content = data.get("site_content")
    if not isinstance(content, dict):
        raise DBError("site_content section is missing from database")
    return content
