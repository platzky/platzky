"""Feature flags system with instance-based registration.

Flags are created as instances of ``FeatureFlag``. Each instance is
automatically registered and discovered via ``all_flags()``. The primary
API is ``engine.is_enabled(flag_instance)``.

Example::

    CategoriesHelp = FeatureFlag(alias="CATEGORIES_HELP")

    # Usage
    app.is_enabled(CategoriesHelp)  # True/False
"""

from __future__ import annotations

_registry: set[FeatureFlag] = set()


class FeatureFlag:
    """A feature flag.

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
        register: bool = True,
    ) -> None:
        if not alias:
            raise ValueError("FeatureFlag requires a non-empty 'alias'")
        self.alias = alias
        self.default = default
        self.description = description
        self.production_warning = production_warning
        if register:
            _registry.add(self)

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


def all_flags() -> frozenset[FeatureFlag]:
    """Return all registered feature flags."""
    return frozenset(_registry)


def unregister(flag: FeatureFlag) -> None:
    """Remove a flag from the registry."""
    _registry.discard(flag)


def parse_flags(
    raw_data: dict[str, bool] | None = None,
) -> frozenset[FeatureFlag]:
    """Build a frozenset of *enabled* flags from raw config data.

    Uses ``all_flags()`` for discovery. Unknown keys in *raw_data* are
    silently ignored.

    Args:
        raw_data: Dict of flag alias -> value from config / YAML.

    Returns:
        A frozenset containing the enabled FeatureFlag instances.
    """
    if raw_data is None:
        raw_data = {}

    return frozenset(flag for flag in all_flags() if raw_data.get(flag.alias, flag.default))
