"""The JSON-family document shared by every JSON repository.

`JsonDocument` loads the document once and owns its store and write lock.
`Json` builds one, uses it for its own reads and writes, and hands the same
instance to `JsonBlogRepository`, `JsonSiteConfigRepository` and
`JsonPluginConfigRepository`, so they
all operate on the exact same in-memory dict -- `FileStore.load()` re-reads and
re-parses the file on every call rather than returning a memoized object, so each
repository loading independently would see its own copy. The dict is only ever
mutated in place, never reassigned.

Writes go through `JsonDocument.edit()`, which holds the write lock and persists
the document on success; the lock and store are not exposed.

Each repository owns one top-level section of the document and gets only a `JsonSection`
view of it, so it can neither read nor write the rest.
"""

import copy
import threading
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from types import MappingProxyType, TracebackType
from typing import Any

from platzky.db.exceptions import InvalidDataError
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

        A restore keeps the top-level dict but replaces its values with
        copies from the pre-edit snapshot, so readers must look nested data up
        from `data` on each call rather than hold on to it.

        Returns:
            A context manager whose `__enter__` returns the document dict, to be
            mutated in place.
        """
        return _Edit(self.data, self._store, self._write_lock)


class JsonSection:
    """One top-level section of a `JsonDocument`: all a repository gets to see of it.

    A repository that owns the ``blog`` section holds a `JsonSection` named ``blog``, and can
    neither read nor write anything else in the document.
    """

    def __init__(self, document: JsonDocument, name: str) -> None:
        """Create the view of one section.

        Args:
            document: The loaded document.
            name: The section's key in the document.
        """
        self._document = document
        self._name = name

    @property
    def name(self) -> str:
        """The section's key in the document."""
        return self._name

    @property
    def data(self) -> Mapping[str, Any]:
        """The section, read-only; empty if the document has none.

        Raises:
            InvalidDataError: If the section is present but not an object (null included).
        """
        return MappingProxyType(self._from_full_document(self._document.data))

    @contextmanager
    def edit(self) -> Generator[dict[str, Any]]:
        """Like `JsonDocument.edit()`, but yield only this section, created if missing.

        Yields:
            The section dict, to be mutated in place; the document is persisted on a clean exit
            and restored otherwise.

        Raises:
            InvalidDataError: If the section is present but not an object (null included).
        """
        with self._document.edit() as document:
            document.setdefault(self._name, {})
            yield self._from_full_document(document)

    def _from_full_document(self, document: Mapping[str, Any]) -> dict[str, Any]:
        """Take this section out of the full document.

        Args:
            document: The whole JSON document, all sections included.

        Returns:
            What the document holds under this section's key; empty if it holds nothing.

        Raises:
            InvalidDataError: If it holds something other than an object (null included).
        """
        section = document.get(self._name, {})
        if not isinstance(section, dict):
            raise InvalidDataError(f"{self._name}: Input should be a valid dictionary")
        return section
