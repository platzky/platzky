"""Exceptions raised by database implementations."""

from pydantic import ValidationError


class DBError(Exception):
    """Base class for all database errors."""


class NotFoundError(DBError, ValueError):
    """Requested content does not exist in the database.

    Inherits from ValueError for backward compatibility with code that
    catches ValueError; that base will be dropped in the next major release.
    """


class ReadOnlyStorageError(DBError):
    """The storage does not support writes."""


class InvalidDataError(DBError):
    """The data in the database does not match its format."""

    @classmethod
    def from_validation_error(cls, error: ValidationError, *path: str) -> "InvalidDataError":
        """Build the error from a pydantic one, listing every problem with its full path.

        Args:
            error: The validation error.
            *path: Where the validated value lives, prepended to each problem's location.

        Returns:
            The error; its message has one ``path: problem`` line per problem.
        """
        return cls(
            "\n".join(
                ".".join([*path, *(str(part) for part in problem["loc"])]) + f": {problem['msg']}"
                for problem in error.errors()
            )
        )
