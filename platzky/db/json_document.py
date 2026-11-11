"""The JSON-family document shared by every JSON repository.

`JsonDocument` loads the document once and owns its store and write lock.
`Json` builds one, uses it for its own reads and writes, and hands the same
instance to `JsonBlogRepository`, `JsonSiteConfigRepository` and
`JsonPluginConfigRepository`, so they
all operate on the exact same document -- `FileStore.load()` re-reads and
re-parses the file on every call rather than returning a memoized object, so each
repository loading independently would see its own copy.

Writes go through `JsonDocument.edit()`, which holds the write lock, works on a copy
and makes it the document once it is saved; the lock and store are not exposed.

Each repository owns one top-level section of the document and gets only a `JsonSection`
view of it, so it can neither read nor write the rest.
"""

import copy
import threading
from collections.abc import Generator, Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from typing_extensions import override

from platzky.db.exceptions import InvalidDataError
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
        self._data: dict[str, Any] = store.load()
        self._write_lock = threading.Lock()

    @property
    def data(self) -> dict[str, Any]:
        """The document as last saved.

        An edit replaces this dict once it is saved, so look it up on each read rather than
        keep it.
        """
        return self._data

    @contextmanager
    def edit(self) -> Generator[dict[str, Any]]:
        """Hold the write lock, yield a copy of the document, and make it the document once saved.

        Use as `with document.edit() as data:`. Readers keep seeing the document as it was
        until the copy is saved, so they never see a half-done edit. If the block raises or
        saving fails, the copy is dropped, the document stays as it was and the error
        propagates.

        Yields:
            A copy of the document, to be mutated in place.
        """
        with self._write_lock:
            draft = copy.deepcopy(self._data)
            yield draft
            self._store.save(draft)
            self._data = draft


class JsonSection(Mapping[str, Any]):
    """One top-level section of a `JsonDocument`: all a repository gets to see of it.

    A repository that owns the ``blog`` section holds a `JsonSection` named ``blog``, and can
    neither read nor write anything else in the document. The section is a read-only, live
    mapping of its content in the document as last saved; `edit()` changes it.
    """

    def __init__(self, document: JsonDocument, name: str) -> None:
        """View one section of a loaded document.

        Args:
            document: The loaded document.
            name: The section's key in the document.

        Raises:
            InvalidDataError: If the document holds something other than an object under the
                key (null included).
        """
        if not isinstance(document.data.get(name, {}), dict):
            raise InvalidDataError(f"{name}: Input should be a valid dictionary")
        self._document = document
        self._name = name

    @property
    def name(self) -> str:
        """The section's key in the document."""
        return self._name

    def _content(self) -> Mapping[str, Any]:
        return self._document.data.get(self._name, {})

    @override
    def __getitem__(self, key: str) -> Any:
        return self._content()[key]

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(self._content())

    @override
    def __len__(self) -> int:
        return len(self._content())

    @contextmanager
    def edit(self) -> Generator[dict[str, Any]]:
        """Yield the section in a copy of the document, to change; see `JsonDocument.edit()`.

        Yields:
            The section's content in the copy, created empty if missing, to be mutated in place.
        """
        with self._document.edit() as document:
            yield document.setdefault(self._name, {})
