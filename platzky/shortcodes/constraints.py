"""Constraints a ``ShortcodeAttr`` can declare, so its shortcode only ever sees values it can use.

Each is a container of the values an attribute takes: ``value in constraint`` says whether a
written value may be used, and nothing is rewritten on the way. Its ``str`` finishes the
sentence "must be …", which is how the refusal, the admin help page and the generated docs
all describe it — empty for ``ANY_TEXT``, which rules nothing out.
"""

from dataclasses import dataclass


class AnyText:
    """Every value: the constraint of an attribute that declares none."""

    def __contains__(self, value: object) -> bool:
        """Accept anything."""
        return True

    def __str__(self) -> str:
        """Say nothing, since nothing is ruled out."""
        return ""


ANY_TEXT = AnyText()


@dataclass(frozen=True)
class IntRange:
    """Whole numbers no smaller than ``low`` and, if given, no larger than ``high``."""

    low: int
    high: int | None = None

    def __contains__(self, value: object) -> bool:
        """Accept a number written as bare ASCII digits, within range.

        Args:
            value: The attribute as written.

        Returns:
            Whether it is bare digits, with no sign, space or separator, inside the range.
        """
        # Both halves: ``isdigit`` is true of the Arabic-Indic and full-width digits too,
        # and of superscripts, which ``int`` reads as numbers or a browser does not read
        # at all. ``isascii`` leaves exactly the ten a width or a duration may be written in.
        if not isinstance(value, str) or not (value.isascii() and value.isdigit()):
            return False
        number = int(value)
        return number >= self.low and (self.high is None or number <= self.high)

    def __str__(self) -> str:
        """Describe the accepted values."""
        if self.high is None:
            return f"a whole number, at least {self.low}"
        return f"a whole number from {self.low} to {self.high}"


class OneOf:
    """A fixed set of words, matched exactly."""

    def __init__(self, *choices: str) -> None:
        """Declare the accepted words, in the order they should be listed.

        Args:
            choices: Every accepted word.
        """
        self.choices = choices

    def __contains__(self, value: object) -> bool:
        """Accept one of ``choices``, exactly as declared."""
        return value in self.choices

    def __str__(self) -> str:
        """Describe the accepted values."""
        return f"one of {', '.join(self.choices)}"
