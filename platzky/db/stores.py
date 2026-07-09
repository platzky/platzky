"""Storage transports for the JSON-document database family.

A `DocumentStore` owns *where* a document's bytes live and how they are read
and written. The document's *meaning* (posts, pages, comments, ...) lives in
`platzky.db.json_db.Json` and is transport-agnostic — `Json` and its
subclasses (`JsonFile`, `GoogleJsonDb`, `GithubJsonDb`, ...) only differ in
which store they hand to the base class.
"""

import json
import os
import tempfile
import threading
from typing import Any, Protocol

from platzky.db.exceptions import ReadOnlyStorageError


class DocumentStore(Protocol):
    """A place a JSON document can be loaded from and saved to."""

    def load(self) -> dict[str, Any]:
        """Read and return the current document."""
        ...

    def save(self, data: dict[str, Any]) -> None:
        """Persist the document.

        Raises:
            ReadOnlyStorageError: If this store does not support writes.
        """
        ...


class MemoryStore:
    """Keeps the document only in memory; nothing is ever persisted.

    This is the store behind the plain in-memory `Json(data)` backend: writes
    succeed (the caller's dict is simply the source of truth) but are not
    written to any external resource.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def load(self) -> dict[str, Any]:
        return self._data

    def save(self, data: dict[str, Any]) -> None:
        self._data = data


class ReadOnlyStore:
    """Wraps a document that was already fetched by the caller and cannot be
    written back.

    Used for backends whose fetch is a one-shot download performed by the
    caller before construction (e.g. a GCS blob or a GitHub file) — the store
    itself does no I/O, it just enforces that writes fail loudly instead of
    silently vanishing.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def load(self) -> dict[str, Any]:
        return self._data

    def save(self, data: dict[str, Any]) -> None:  # noqa: ARG002
        raise ReadOnlyStorageError("This storage backend does not support writes.")


class FileStore:
    """A JSON document stored in a local file, written atomically.

    `save()` writes to a temporary file in the same directory and atomically
    renames it over the target, so a crash mid-write cannot corrupt the file.
    A lock serializes writes from this process (multi-process coordination is
    out of scope: `json_file` is positioned as the local/single-instance
    backend).
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> dict[str, Any]:
        with open(self.path, "r") as f:
            return json.load(f)

    def save(self, data: dict[str, Any]) -> None:
        dir_name = os.path.dirname(self.path) or "."
        with self._lock:
            tmp_file = tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False)
            try:
                json.dump(data, tmp_file)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
                tmp_file.close()
                os.replace(tmp_file.name, self.path)
            except BaseException:
                tmp_file.close()
                if os.path.exists(tmp_file.name):
                    os.remove(tmp_file.name)
                raise
