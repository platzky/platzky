"""Exceptions raised by database implementations."""

from collections.abc import Callable, Iterable

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


def format_problems(error: ValidationError, *path: str) -> str:
    """List every problem of a pydantic validation error with its full path, one per line.

    Args:
        error: The validation error.
        *path: Where the validated value lives, prepended to each problem's location.

    Returns:
        One ``path: problem`` line per problem.
    """
    return "\n".join(
        ".".join([*path, *(str(part) for part in problem["loc"])]) + f": {problem['msg']}"
        for problem in error.errors()
    )


def validate_all(validators: Iterable[Callable[[], object]]) -> None:
    """Run every validator, so that all problems are reported together.

    Args:
        validators: Callables that raise `InvalidDataError` when their data is invalid.

    Raises:
        InvalidDataError: If any is invalid; the message has the problems of all of them.
    """
    problems: list[str] = []
    for validate in validators:
        try:
            validate()
        except InvalidDataError as error:
            problems.append(str(error))
    if problems:
        raise InvalidDataError("\n".join(problems))
