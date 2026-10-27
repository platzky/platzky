"""The JSON-family document shared by every JSON repository.

`JsonDocument` loads the document once and owns its store and write lock.
`Json` builds one, uses it for its own reads and writes, and hands the same
instance to `JsonSiteConfigRepository` and `JsonPluginConfigRepository`, so they
all operate on the exact same in-memory dict -- `FileStore.load()` re-reads and
re-parses the file on every call rather than returning a memoized object, so each
repository loading independently would see its own copy. The dict is only ever
mutated in place, never reassigned.

Writes go through `JsonDocument.edit()`, which holds the write lock and persists
the document on success; the lock and store are not exposed.

`get_site_content` is the shared "read site_content, raise if missing" helper
used by those repositories and `Json.health_check`.
"""

import copy
import threading
from collections.abc import Generator
from contextlib import contextmanager
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
        self._store: JsonStore = store
        self.data: dict[str, Any] = store.load()
        self._write_lock = threading.Lock()

    @contextmanager
    def edit(self) -> Generator[dict[str, Any], None, None]:
        """Hold the write lock, yield the document, and persist it on success.

        If the body raises, nothing is saved and the exception propagates. If
        saving fails, the document is restored in place (same dict object) to
        its state before the edit, and the error propagates.

        Yields:
            The document dict, to be mutated in place.
        """
        with self._write_lock:
            snapshot = copy.deepcopy(self.data)
            try:
                yield self.data
                self._store.save(self.data)
            except BaseException:
                # Restore key by key rather than clear() + update(): readers
                # don't take the lock and must never see an empty document.
                for key in self.data.keys() - snapshot.keys():
                    del self.data[key]
                self.data.update(snapshot)
                raise


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
