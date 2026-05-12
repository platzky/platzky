"""Feature flag set container."""

from platzky.feature_flags import FeatureFlag


class FeatureFlagSet(dict[str, bool]):
    """Immutable feature flag collection (dict subclass).

    Dual-mode container:
    - ``FeatureFlag in flag_set`` — typed membership check (primary API via engine.is_enabled).
    - ``flag_set["KEY"]`` / ``flag_set.get("KEY")`` — raw dict access for config introspection.
    """

    def __init__(self, raw_data: dict[str, bool]) -> None:
        super().__init__(raw_data)

    def _raise_immutable(self, *_args: object, **_kwargs: object) -> None:
        """Prevent mutation — FeatureFlagSet is read-only."""
        raise TypeError("FeatureFlagSet is immutable")

    __setitem__ = _raise_immutable
    __delitem__ = _raise_immutable
    pop = _raise_immutable  # type: ignore[assignment]
    update = _raise_immutable  # type: ignore[assignment]
    clear = _raise_immutable
    setdefault = _raise_immutable  # type: ignore[assignment]
    __ior__ = _raise_immutable  # type: ignore[assignment]

    def __contains__(self, item: object) -> bool:
        """Support both FeatureFlag membership and string key lookup."""
        if isinstance(item, FeatureFlag):
            if super().__contains__(item.alias):
                return bool(super().__getitem__(item.alias))
            return item.default
        return super().__contains__(item)
