"""Feature flags system for Platzky.

Flags are created as instances of ``FeatureFlag``. The primary API is
``engine.is_enabled(flag_instance)``.  Resolution is dynamic — the
``FeatureFlagSet`` checks the raw config dict using each flag's ``alias``
and ``default`` at lookup time.  No global registry is needed.

Example::

    CategoriesHelp = FeatureFlag(alias="CATEGORIES_HELP")

    # Usage
    app.is_enabled(CategoriesHelp)  # True/False
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import deprecation

if TYPE_CHECKING:
    from platzky.feature_flags_wrapper import FeatureFlagSet


class FeatureFlag:
    """A feature flag.

    Identity is based solely on ``alias``: two flags with the same alias
    are considered equal regardless of ``default`` or ``description``.
    Aliases are expected to be unique across the application.

    Args:
        alias: The YAML/dict key for this flag.
        default: Whether the flag is enabled by default.
        description: Human-readable description.

    Example::

        FakeLogin = FeatureFlag(
            alias="FAKE_LOGIN",
            default=False,
            description="Enable fake login. Never in production.",
        )
    """

    __slots__ = ("alias", "default", "description", "production_warning")

    def __init__(
        self,
        *,
        alias: str,
        default: bool = False,
        description: str = "",
        production_warning: bool = False,
    ) -> None:
        if not alias:
            raise ValueError("FeatureFlag requires a non-empty 'alias'")
        self.alias = alias
        self.default = default
        self.description = description
        self.production_warning = production_warning

    def __repr__(self) -> str:
        return f"FeatureFlag(alias={self.alias!r})"

    def __hash__(self) -> int:
        return hash(self.alias)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FeatureFlag):
            return self.alias == other.alias
        return NotImplemented


FakeLogin = FeatureFlag(
    alias="FAKE_LOGIN",
    default=False,
    description="Enable fake login for development. WARNING: Never enable in production.",
    production_warning=True,
)

BUILTIN_FLAGS: tuple[FeatureFlag, ...] = (FakeLogin,)


# ---------------------------------------------------------------------------
# Deprecated shims — will be removed in 2.0.0
# ---------------------------------------------------------------------------


@deprecation.deprecated(
    deprecated_in="1.5.0",
    removed_in="2.0.0",
    details="Use BUILTIN_FLAGS instead.",
)
def all_flags() -> frozenset[FeatureFlag]:
    """Return all built-in feature flags."""
    return frozenset(BUILTIN_FLAGS)


@deprecation.deprecated(
    deprecated_in="1.5.0",
    removed_in="2.0.0",
    details="Use FeatureFlagSet(raw_data) and check membership with 'flag in flag_set' instead.",
)
def parse_flags(
    raw_data: dict[str, bool] | None = None,
) -> frozenset[FeatureFlag]:
    """Build a frozenset of enabled flags from raw config data."""
    if raw_data is None:
        raw_data = {}
    return frozenset(flag for flag in BUILTIN_FLAGS if raw_data.get(flag.alias, flag.default))


@deprecation.deprecated(
    deprecated_in="1.5.0",
    removed_in="2.0.0",
    details="Use FeatureFlagSet(raw_data) directly.",
)
def build_flag_set(raw_data: dict[str, bool] | None = None) -> FeatureFlagSet:
    """Build a FeatureFlagSet from raw config data."""
    from platzky.feature_flags_wrapper import FeatureFlagSet

    return FeatureFlagSet(raw_data or {})


@deprecation.deprecated(
    deprecated_in="1.5.0",
    removed_in="2.0.0",
    details="No replacement needed — the global registry has been removed.",
)
def unregister(_flag: FeatureFlag) -> None:
    """No-op. The global registry has been removed."""


@deprecation.deprecated(
    deprecated_in="1.5.0",
    removed_in="2.0.0",
    details="No replacement needed — the global registry has been removed.",
)
def clear_registry() -> None:
    """No-op. The global registry has been removed."""
