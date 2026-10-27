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
from types import TracebackType
from typing import Any

from platzky.db.exceptions import DBError
from platzky.db.json_stores import JsonStore


class _Edit:
    """Context manager for one `JsonDocument.edit()` call.

    A class rather than a `@contextmanager` generator so every exit path is an
    explicit branch of `__exit__`: save on a clean exit (including `return` or
    `break` inside the block), restore when the block raises or the save fails,
    and release the lock in every case.
    """

    def __init__(self, data: dict[str, Any], store: JsonStore, lock: threading.Lock) -> None:
        self._data = data
        self._store = store
        self._lock = lock
        self._snapshot: dict[str, Any] = {}

    def __enter__(self) -> dict[str, Any]:
        self._lock.acquire()
        try:
            self._snapshot = copy.deepcopy(self._data)
        except BaseException:
            self._lock.release()
            raise
        return self._data

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                self._restore()
                return
            try:
                self._store.save(self._data)
            except BaseException:
                self._restore()
                raise
        finally:
            self._lock.release()

    def _restore(self) -> None:
        # Restore key by key rather than clear() + update(): readers don't take
        # the lock and must never see an empty document.
        for key in self._data.keys() - self._snapshot.keys():
            del self._data[key]
        self._data.update(self._snapshot)


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

    def edit(self) -> _Edit:
        """Hold the write lock, yield the document, and persist it on success.

        Use as `with document.edit() as data:`. If the body raises, nothing is
        saved, the document is restored in place (same dict object) to its
        state before the edit, and the exception propagates. If saving fails,
        the document is restored the same way and the error propagates.

        Returns:
            A context manager whose `__enter__` returns the document dict, to be
            mutated in place.
        """
        return _Edit(self.data, self._store, self._write_lock)


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
