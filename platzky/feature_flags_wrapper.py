"""Backward-compatible wrapper for feature flags.

.. deprecated:: 1.4.0
    Dict-like access is deprecated. Use typed FeatureFlag instances
    with engine.is_enabled(flag) instead.
"""

import warnings

import deprecation

from platzky.feature_flags import FeatureFlag

_MIGRATION_MSG = (
    "Dict-like access to feature flags is deprecated. "
    "Define a FeatureFlag instance and use engine.is_enabled(flag) instead. "
    "See: https://platzky.readthedocs.io/en/latest/config.html#feature-flags"
)

_DEPRECATION_WARNING = deprecation.DeprecatedWarning(
    "feature_flags dict access",
    "1.4.0",
    "2.0.0",
    _MIGRATION_MSG,
)


def _warn_dict_access() -> None:
    warnings.warn(_DEPRECATION_WARNING, stacklevel=3)


class FeatureFlagSet(dict[str, bool]):
    """Backward-compatible feature flag collection (dict subclass).

    .. deprecated:: 1.4.0
        Dict-like access (.get, .KEY, [key]) is deprecated.
        Migrate to typed FeatureFlag + engine.is_enabled().

    Dual-mode container:
    - ``FeatureFlag in flag_set`` -- typed membership (engine.is_enabled). Intended API.
    - ``flag_set.get("KEY")`` -- deprecated dict access via dict inheritance.
    - ``flag_set.KEY`` -- deprecated Jinja2 attribute access.
    """

    def __init__(self, raw_data: dict[str, bool]) -> None:
        super().__init__(raw_data)

    def __getitem__(self, key: str) -> bool:
        """Dict bracket access with deprecation warning."""
        _warn_dict_access()
        return super().__getitem__(key)

    def get(self, key: str, default: bool | None = None) -> bool | None:  # type: ignore[override]
        """Dict .get() access with deprecation warning."""
        _warn_dict_access()
        return super().get(key, default)

    def _raise_immutable(self, *_args: object, **_kwargs: object) -> None:
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

    def __getattr__(self, name: str) -> bool:
        """Jinja2 dot-notation access: ``{{ feature_flags.SOME_FLAG }}``."""
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' has no attribute {name!r}") from None
