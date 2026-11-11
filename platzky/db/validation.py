"""Validation of the data stored in a database."""

from collections.abc import Callable, Iterable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from platzky.db.exceptions import InvalidDataError

M = TypeVar("M", bound=BaseModel)


def _format_problems(error: ValidationError, *path: str) -> str:
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


def parse(model: type[M], data: object, *path: str) -> M:
    """Validate stored data as `model`.

    Args:
        model: The pydantic model the data must match.
        data: The stored data.
        *path: Where the data lives, prepended to each problem's location.

    Returns:
        The validated model.

    Raises:
        InvalidDataError: If it is invalid; the message lists every problem with its path
            (``path`` prepended), one per line.
    """
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise InvalidDataError(_format_problems(error, *path)) from error


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
