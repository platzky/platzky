"""Exceptions raised by database implementations."""


class DBError(Exception):
    """Base class for all database errors."""


class NotFoundError(DBError, ValueError):
    """Requested content does not exist in the database.

    Inherits from ValueError for backward compatibility with code that
    catches ValueError; that base will be dropped in the next major release.
    """


class ReadOnlyStorageError(DBError):
    """The backing store does not support writes."""
