"""Feature flags system with class-based flag registration.

Flags are defined as classes deriving from ``Flag``. Any ``Flag`` subclass
is automatically discovered via ``all_flags()``. The primary API is
``engine.is_enabled(FlagClass)``.

Example::

    class CategoriesHelp(Flag):
        alias = "CATEGORIES_HELP"
        default = False

    # Usage — no Config subclass needed
    app.is_enabled(CategoriesHelp)  # True/False
"""

from __future__ import annotations

from typing import ClassVar


class Flag:
    """Base class for feature flags.

    Subclasses must define ``alias`` (the YAML/dict key).
    Optional: ``default`` (bool, defaults to False), ``description`` (str).

    Example::

        class FakeLogin(Flag):
            alias = "FAKE_LOGIN"
            default = False
            description = "Enable fake login. Never in production."
    """

    alias: ClassVar[str]
    default: ClassVar[bool] = False
    description: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Validate that subclasses define ``alias``."""
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "alias") or not cls.alias:
            raise TypeError(f"Flag subclass {cls.__name__!r} must define a non-empty 'alias' str")


class FakeLogin(Flag):
    """Enable fake login for development."""

    alias = "FAKE_LOGIN"
    default = False
    description = "Enable fake login for development. WARNING: Never enable in production."


def all_flags() -> tuple[type[Flag], ...]:
    """Return all valid Flag subclasses via automatic discovery.

    Skips subclasses that failed validation (e.g. missing ``alias``).
    """
    return tuple(cls for cls in Flag.__subclasses__() if hasattr(cls, "alias") and cls.alias)


def parse_flags(
    flag_types: tuple[type[Flag], ...],
    raw_data: dict[str, bool] | None = None,
) -> frozenset[type[Flag]]:
    """Build a frozenset of *enabled* flag types from raw config data.

    Unknown keys in *raw_data* are silently ignored.

    Args:
        flag_types: Tuple of Flag subclasses to consider.
        raw_data: Dict of flag alias -> value from config / YAML.

    Returns:
        A frozenset containing the Flag subclasses that are enabled.
    """
    if raw_data is None:
        raw_data = {}

    enabled: set[type[Flag]] = set()
    for flag_cls in flag_types:
        value = bool(raw_data.get(flag_cls.alias, flag_cls.default))
        if value:
            enabled.add(flag_cls)

    return frozenset(enabled)
