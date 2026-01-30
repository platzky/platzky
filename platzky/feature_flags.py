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

import warnings
from typing import Any, ClassVar

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


class FeatureFlags:
    """Immutable container for feature flag values.

    Provides class-based lookup (primary API) and serialization helpers.
    For backward-compatible string access, use ``FeatureFlagsCompat``.

    Args:
        flag_types: Tuple of Flag subclasses to register.
        raw_data: Dict of flag alias -> value from config / YAML.
    """

    __slots__ = ("_values", "_alias_to_flag", "_unregistered")

    def __init__(
        self,
        flag_types: tuple[type[Flag], ...],
        raw_data: dict[str, bool] | None = None,
    ) -> None:
        if raw_data is None:
            raw_data = {}

        alias_to_flag: dict[str, type[Flag]] = {}
        values: dict[type[Flag], bool] = {}

        for flag_cls in flag_types:
            alias_to_flag[flag_cls.alias] = flag_cls
            values[flag_cls] = bool(raw_data.get(flag_cls.alias, flag_cls.default))

        unregistered: dict[str, bool] = {}
        for key, val in raw_data.items():
            if key not in alias_to_flag:
                unregistered[key] = bool(val)

        object.__setattr__(self, "_values", values)
        object.__setattr__(self, "_alias_to_flag", alias_to_flag)
        object.__setattr__(self, "_unregistered", unregistered)

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent mutation."""
        raise AttributeError("FeatureFlags is immutable")

    def __delattr__(self, name: str) -> None:
        """Prevent deletion."""
        raise AttributeError("FeatureFlags is immutable")

    # -- Primary API ----------------------------------------------------------

    def __getitem__(self, flag_type: type[Flag]) -> bool:
        """Typed lookup by Flag class.

        Args:
            flag_type: A Flag subclass that was registered.

        Returns:
            The flag value.

        Raises:
            KeyError: If the flag class was not registered.
        """
        try:
            return self._values[flag_type]
        except KeyError:
            raise KeyError(
                f"Flag {flag_type.__name__!r} (alias={flag_type.alias!r}) is not registered. "
                f"Add it to _flag_types on your Config subclass."
            ) from None

    # -- Serialization --------------------------------------------------------

    def to_dict(self) -> dict[str, bool]:
        """Return all flags as a ``{alias: value}`` dict.

        Includes both registered and unregistered flags.
        """
        result: dict[str, bool] = {}
        for flag_cls, val in self._values.items():
            result[flag_cls.alias] = val
        result.update(self._unregistered)
        return result

    def get_all(self) -> dict[str, dict[str, bool | str | None]]:
        """Return all flags with metadata, suitable for admin panels.

        Returns:
            Dict mapping flag alias to metadata dict with keys:
            ``value``, ``description``, ``default``, ``alias``, ``typed``.
        """
        result: dict[str, dict[str, bool | str | None]] = {}
        for flag_cls, val in self._values.items():
            result[flag_cls.alias] = {
                "value": val,
                "description": flag_cls.description,
                "default": flag_cls.default,
                "alias": flag_cls.alias,
                "typed": True,
            }
        for key, val in self._unregistered.items():
            result[key] = {
                "value": val,
                "description": "(Unregistered flag - deprecated)",
                "default": None,
                "alias": key,
                "typed": False,
            }
        return result

    # -- Dunder methods -------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        """Support comparison with dict."""
        if isinstance(other, FeatureFlags):
            return self.to_dict() == other.to_dict()
        if isinstance(other, dict):
            return self.to_dict() == other
        return NotImplemented

    def __repr__(self) -> str:
        return f"FeatureFlags({self.to_dict()!r})"

    def __bool__(self) -> bool:
        """True if any flag is enabled."""
        return any(self._values.values()) or any(self._unregistered.values())

    # -- Pydantic integration -------------------------------------------------

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,  # noqa: ANN401
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Pydantic core schema: accept FeatureFlags or coerce from dict."""
        return core_schema.union_schema(
            [
                core_schema.is_instance_schema(FeatureFlags),
                core_schema.chain_schema(
                    [
                        core_schema.dict_schema(),
                        core_schema.no_info_plain_validator_function(
                            lambda v: FeatureFlags(BUILTIN_FLAGS, v)
                        ),
                    ]
                ),
            ],
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: v.to_dict(), info_arg=False
            ),
        )


class FeatureFlagsCompat:
    """Backward-compatible wrapper around ``FeatureFlags``.

    Adds ``.is_enabled()``, ``.get(key, default)``, and attribute access
    (``__getattr__``) for Jinja templates and legacy code.

    Args:
        inner: The ``FeatureFlags`` instance to wrap.
    """

    __slots__ = ("_inner",)

    def __init__(self, inner: FeatureFlags) -> None:
        object.__setattr__(self, "_inner", inner)

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent mutation."""
        raise AttributeError("FeatureFlagsCompat is immutable")

    def __delattr__(self, name: str) -> None:
        """Prevent deletion."""
        raise AttributeError("FeatureFlagsCompat is immutable")

    # -- Delegated core API ---------------------------------------------------

    def __getitem__(self, flag_type: type[Flag]) -> bool:
        return self._inner[flag_type]

    def to_dict(self) -> dict[str, bool]:
        return self._inner.to_dict()

    def get_all(self) -> dict[str, dict[str, bool | str | None]]:
        return self._inner.get_all()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FeatureFlagsCompat):
            return self._inner == other._inner
        if isinstance(other, FeatureFlags):
            return self._inner == other
        if isinstance(other, dict):
            return self._inner == other
        return NotImplemented

    def __repr__(self) -> str:
        return f"FeatureFlagsCompat({self._inner.to_dict()!r})"

    def __bool__(self) -> bool:
        return bool(self._inner)

    # -- Backward-compatible methods ------------------------------------------

    def is_enabled(self, flag_type: type[Flag]) -> bool:
        """Check whether a flag is enabled. Same as ``__getitem__``.

        Args:
            flag_type: A Flag subclass that was registered.

        Returns:
            The flag value.
        """
        return self._inner[flag_type]

    def get(self, key: str, default: bool = False) -> bool:
        """Dict-like access by alias string.

        Registered flags are returned directly. Unregistered flags emit a
        deprecation warning.

        Args:
            key: Flag alias (e.g. ``"FAKE_LOGIN"``).
            default: Default value if the flag is not found at all.

        Returns:
            The flag value.
        """
        flag_cls = self._inner._alias_to_flag.get(key)
        if flag_cls is not None:
            return self._inner._values[flag_cls]

        if key in self._inner._unregistered:
            flag_name = key.lower().replace("-", "_")
            warnings.warn(
                f"Unregistered feature flag '{key}' is deprecated. "
                f"Unregistered flags will be removed in version 2.0.0. "
                f"To migrate, define a Flag class:\n"
                f"  class {flag_name.title().replace('_', '')}(Flag):\n"
                f"      alias = '{key}'\n"
                f"      default = False\n"
                f"Then add it to _flag_types on your Config subclass.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self._inner._unregistered[key]

        return default

    def __getattr__(self, name: str) -> bool:
        """Attribute access for Jinja templates.

        Supports both alias (``flags.FAKE_LOGIN``) and lowercase
        (``flags.fake_login``).

        Args:
            name: Attribute name.

        Returns:
            The flag value.

        Raises:
            AttributeError: If not found.
        """
        flag_cls = self._inner._alias_to_flag.get(name)
        if flag_cls is not None:
            return self._inner._values[flag_cls]

        upper_name = name.upper()
        flag_cls = self._inner._alias_to_flag.get(upper_name)
        if flag_cls is not None:
            return self._inner._values[flag_cls]

        if name in self._inner._unregistered:
            return self._inner._unregistered[name]
        if upper_name in self._inner._unregistered:
            return self._inner._unregistered[upper_name]

        raise AttributeError(f"FeatureFlagsCompat has no flag '{name}'")
