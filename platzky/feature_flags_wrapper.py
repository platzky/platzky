"""Backward-compatible wrapper for feature flags.

.. deprecated:: 1.5.0
    Dict-like access is deprecated. Use typed FeatureFlag instances
    with engine.is_enabled(flag) instead.
"""

from __future__ import annotations

import deprecation

from platzky.feature_flags import FeatureFlag

_MIGRATION_MSG = (
    "Dict-like access to feature flags is deprecated. "
    "Define a FeatureFlag instance and use engine.is_enabled(flag) instead. "
    "See: https://platzky.readthedocs.io/en/latest/config.html#feature-flags"
)


class FeatureFlagSet(dict[str, bool]):
    """Backward-compatible feature flag collection (dict subclass).

    .. deprecated:: 1.5.0
        Dict-like access (.get, .KEY, [key]) is deprecated.
        Migrate to typed FeatureFlag + engine.is_enabled().

    Dual-mode container:
    - ``FeatureFlag in flag_set`` -- typed membership (engine.is_enabled). Intended API.
    - ``flag_set.get("KEY")`` -- deprecated dict access via dict inheritance.
    - ``flag_set.KEY`` -- deprecated Jinja2 attribute access.
    """

    _enabled_flags: frozenset[FeatureFlag]

    @deprecation.deprecated(
        deprecated_in="1.5.0",
        removed_in="2.0.0",
        current_version="1.5.0",
        details=_MIGRATION_MSG,
    )
    def __init__(
        self,
        enabled_flags: frozenset[FeatureFlag],
        raw_data: dict[str, bool],
    ) -> None:
        super().__init__(raw_data)
        # Use object.__setattr__ to bypass any future __setattr__ override
        object.__setattr__(self, "_enabled_flags", enabled_flags)

    def __contains__(self, item: object) -> bool:
        """Support both FeatureFlag membership and string key lookup."""
        if isinstance(item, FeatureFlag):
            return item in self._enabled_flags
        return super().__contains__(item)

    def __getattr__(self, name: str) -> bool:
        """Jinja2 dot-notation access: ``{{ feature_flags.SOME_FLAG }}``."""
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' has no attribute {name!r}") from None

    @property
    def enabled_flags(self) -> frozenset[FeatureFlag]:
        """The set of enabled typed FeatureFlag instances."""
        return self._enabled_flags
