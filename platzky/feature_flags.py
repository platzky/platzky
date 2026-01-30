"""Feature flags system with class-based flag registration.

Flags are defined as classes deriving from ``Flag``. Clients register flags via
a ``_flag_types`` tuple on their ``Config`` subclass. The primary API is
``engine.is_enabled(FlagClass)``.

Example::

    class CategoriesHelp(Flag):
        alias = "CATEGORIES_HELP"
        default = False

    class GoodmapConfig(PlatzkyConfig):
        _flag_types = PlatzkyConfig._flag_types + (CategoriesHelp,)

    # Usage
    app.is_enabled(CategoriesHelp)  # True/False
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


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


BUILTIN_FLAGS: tuple[type[Flag], ...] = (FakeLogin,)


# ---------------------------------------------------------------------------
# Standalone functions
# ---------------------------------------------------------------------------


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


def flags_to_dict(
    enabled: frozenset[type[Flag]],
    flag_types: tuple[type[Flag], ...],
) -> dict[str, bool]:
    """Serialize enabled flags as ``{alias: bool}`` for every registered type.

    Args:
        enabled: The frozenset of enabled Flag subclasses.
        flag_types: All registered Flag subclasses.

    Returns:
        Dict mapping each flag alias to its enabled status.
    """
    return {flag_cls.alias: (flag_cls in enabled) for flag_cls in flag_types}


def get_all_flags_metadata(
    enabled: frozenset[type[Flag]],
    flag_types: tuple[type[Flag], ...],
) -> dict[str, dict[str, bool | str]]:
    """Return all flags with metadata, suitable for admin panels.

    Args:
        enabled: The frozenset of enabled Flag subclasses.
        flag_types: All registered Flag subclasses.

    Returns:
        Dict mapping flag alias to metadata dict with keys:
        ``value``, ``description``, ``default``, ``alias``.
    """
    result: dict[str, dict[str, bool | str]] = {}
    for flag_cls in flag_types:
        result[flag_cls.alias] = {
            "value": flag_cls in enabled,
            "description": flag_cls.description,
            "default": flag_cls.default,
            "alias": flag_cls.alias,
        }
    return result


# ---------------------------------------------------------------------------
# Pydantic integration
# ---------------------------------------------------------------------------


class _EnabledFlagsMarker:
    """Pydantic schema marker: accept frozenset[type[Flag]] or coerce from dict.

    Serialises as ``{alias: True}`` for each enabled flag (builtin types only).
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,  # noqa: ANN401
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Pydantic core schema: accept frozenset or coerce from dict."""
        return core_schema.union_schema(
            [
                core_schema.is_instance_schema(frozenset),
                core_schema.chain_schema(
                    [
                        core_schema.dict_schema(),
                        core_schema.no_info_plain_validator_function(
                            lambda v: parse_flags(BUILTIN_FLAGS, v)
                        ),
                    ]
                ),
            ],
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: flags_to_dict(v, BUILTIN_FLAGS), info_arg=False
            ),
        )


EnabledFlags = Annotated[frozenset[type[Flag]], _EnabledFlagsMarker]
"""Type alias for a frozenset of enabled Flag types, with Pydantic support."""
