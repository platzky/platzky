import warnings

import pytest

from platzky.config import Config, languages_dict
from platzky.feature_flags import FakeLogin, FeatureFlags, FeatureFlagsCompat, Flag


class TestFlagSubclass:
    """Tests for Flag.__init_subclass__ validation."""

    def test_valid_flag(self) -> None:
        """Test that a valid Flag subclass can be created."""

        class MyFlag(Flag):
            alias = "MY_FLAG"
            default = True
            description = "A test flag."

        assert MyFlag.alias == "MY_FLAG"
        assert MyFlag.default is True
        assert MyFlag.description == "A test flag."

    def test_flag_without_alias_raises(self) -> None:
        """Test that Flag subclass without alias raises TypeError."""
        with pytest.raises(TypeError, match="must define a non-empty 'alias'"):

            class BadFlag(Flag):
                pass

    def test_flag_with_empty_alias_raises(self) -> None:
        """Test that Flag subclass with empty alias raises TypeError."""
        with pytest.raises(TypeError, match="must define a non-empty 'alias'"):

            class BadFlag(Flag):
                alias = ""

    def test_flag_defaults(self) -> None:
        """Test that Flag subclass inherits defaults."""

        class MinimalFlag(Flag):
            alias = "MINIMAL"

        assert MinimalFlag.default is False
        assert MinimalFlag.description == ""


class TestFeatureFlags:
    """Tests for FeatureFlags core container (no backward compat)."""

    def test_construction_with_defaults(self) -> None:
        """Test FeatureFlags uses defaults when no raw_data."""
        ff = FeatureFlags((FakeLogin,), {})
        assert ff[FakeLogin] is False

    def test_construction_with_override(self) -> None:
        """Test FeatureFlags picks up values from raw_data."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        assert ff[FakeLogin] is True

    def test_getitem_unregistered_raises(self) -> None:
        """Test that looking up an unregistered Flag class raises KeyError."""

        class Unregistered(Flag):
            alias = "UNREG"

        ff = FeatureFlags((FakeLogin,), {})
        with pytest.raises(KeyError, match="not registered"):
            ff[Unregistered]

    def test_immutability(self) -> None:
        """Test that FeatureFlags cannot be mutated."""
        ff = FeatureFlags((FakeLogin,), {})
        with pytest.raises(AttributeError, match="immutable"):
            ff.FAKE_LOGIN = True

    def test_to_dict(self) -> None:
        """Test to_dict() returns all flags."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True, "CUSTOM": True})
        d = ff.to_dict()
        assert d == {"FAKE_LOGIN": True, "CUSTOM": True}

    def test_eq_with_dict(self) -> None:
        """Test __eq__ supports dict comparison."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True, "CUSTOM": True})
        assert ff == {"FAKE_LOGIN": True, "CUSTOM": True}

    def test_eq_with_feature_flags(self) -> None:
        """Test __eq__ supports FeatureFlags comparison."""
        ff1 = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        ff2 = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        assert ff1 == ff2

    def test_repr(self) -> None:
        """Test __repr__."""
        ff = FeatureFlags((FakeLogin,), {})
        assert "FAKE_LOGIN" in repr(ff)

    def test_get_all(self) -> None:
        """Test get_all() returns metadata."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True, "CUSTOM": True})
        all_flags = ff.get_all()

        assert "FAKE_LOGIN" in all_flags
        assert all_flags["FAKE_LOGIN"]["value"] is True
        assert all_flags["FAKE_LOGIN"]["typed"] is True
        assert all_flags["FAKE_LOGIN"]["alias"] == "FAKE_LOGIN"

        assert "CUSTOM" in all_flags
        assert all_flags["CUSTOM"]["value"] is True
        assert all_flags["CUSTOM"]["typed"] is False

    def test_pydantic_core_schema_passthrough(self) -> None:
        """Test that __get_pydantic_core_schema__ passes through FeatureFlags instances."""
        from pydantic import BaseModel, ConfigDict, Field

        class TestModel(BaseModel):
            model_config = ConfigDict(frozen=True)
            flags: FeatureFlags = Field(default_factory=lambda: FeatureFlags((), {}))

        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        m = TestModel(flags=ff)
        assert m.flags is ff
        assert m.flags[FakeLogin] is True

    def test_pydantic_core_schema_dict_coercion(self) -> None:
        """Test that __get_pydantic_core_schema__ coerces dicts to FeatureFlags."""
        from pydantic import BaseModel, ConfigDict, Field

        class TestModel(BaseModel):
            model_config = ConfigDict(frozen=True)
            flags: FeatureFlags = Field(default_factory=lambda: FeatureFlags((), {}))

        m = TestModel(flags={"FAKE_LOGIN": True})  # type: ignore[arg-type]
        assert isinstance(m.flags, FeatureFlags)
        assert m.flags.to_dict() == {"FAKE_LOGIN": True}

    def test_pydantic_core_schema_serialization(self) -> None:
        """Test that __get_pydantic_core_schema__ serializes via to_dict()."""
        from pydantic import BaseModel, ConfigDict, Field

        class TestModel(BaseModel):
            model_config = ConfigDict(frozen=True)
            flags: FeatureFlags = Field(default_factory=lambda: FeatureFlags((), {}))

        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        m = TestModel(flags=ff)
        dumped = m.model_dump()
        assert dumped["flags"] == {"FAKE_LOGIN": True}


class TestFeatureFlagsCompat:
    """Tests for FeatureFlagsCompat backward-compatible wrapper."""

    def test_is_enabled(self) -> None:
        """Test is_enabled method."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        compat = FeatureFlagsCompat(ff)
        assert compat.is_enabled(FakeLogin) is True

    def test_getitem(self) -> None:
        """Test __getitem__ delegation."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        compat = FeatureFlagsCompat(ff)
        assert compat[FakeLogin] is True

    def test_get_registered_by_alias(self) -> None:
        """Test .get() returns value for registered flag by alias."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        compat = FeatureFlagsCompat(ff)
        assert compat.get("FAKE_LOGIN") is True

    def test_get_registered_no_warning(self) -> None:
        """Test .get() does not warn for registered flags."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        compat = FeatureFlagsCompat(ff)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            compat.get("FAKE_LOGIN")
            assert len(w) == 0

    def test_get_unregistered_warns(self) -> None:
        """Test .get() emits deprecation warning for unregistered flags."""
        ff = FeatureFlags((FakeLogin,), {"CUSTOM_FLAG": True})
        compat = FeatureFlagsCompat(ff)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = compat.get("CUSTOM_FLAG")
            assert result is True
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "CUSTOM_FLAG" in str(w[0].message)
            assert "2.0.0" in str(w[0].message)

    def test_get_unknown_returns_default(self) -> None:
        """Test .get() returns default for completely unknown flags."""
        ff = FeatureFlags((FakeLogin,), {})
        compat = FeatureFlagsCompat(ff)
        assert compat.get("UNKNOWN", False) is False
        assert compat.get("UNKNOWN", True) is True

    def test_get_positional_default(self) -> None:
        """Test .get() accepts default as positional argument."""
        ff = FeatureFlags((FakeLogin,), {})
        compat = FeatureFlagsCompat(ff)
        # default is positional (not keyword-only) in compat
        assert compat.get("UNKNOWN", True) is True

    def test_getattr_alias(self) -> None:
        """Test attribute access by alias."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        compat = FeatureFlagsCompat(ff)
        assert compat.FAKE_LOGIN is True

    def test_getattr_lowercase(self) -> None:
        """Test attribute access by lowercase name."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        compat = FeatureFlagsCompat(ff)
        assert compat.fake_login is True

    def test_getattr_missing_raises(self) -> None:
        """Test attribute access for missing flag raises AttributeError."""
        ff = FeatureFlags((FakeLogin,), {})
        compat = FeatureFlagsCompat(ff)
        with pytest.raises(AttributeError, match="no flag"):
            compat.nonexistent

    def test_immutability(self) -> None:
        """Test that FeatureFlagsCompat cannot be mutated."""
        ff = FeatureFlags((FakeLogin,), {})
        compat = FeatureFlagsCompat(ff)
        with pytest.raises(AttributeError, match="immutable"):
            compat.FAKE_LOGIN = True

    def test_to_dict(self) -> None:
        """Test to_dict() delegation."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True, "CUSTOM": True})
        compat = FeatureFlagsCompat(ff)
        assert compat.to_dict() == {"FAKE_LOGIN": True, "CUSTOM": True}

    def test_eq_with_dict(self) -> None:
        """Test __eq__ supports dict comparison."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        compat = FeatureFlagsCompat(ff)
        assert compat == {"FAKE_LOGIN": True}

    def test_eq_with_feature_flags(self) -> None:
        """Test __eq__ supports FeatureFlags comparison."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        compat = FeatureFlagsCompat(ff)
        assert compat == ff

    def test_repr(self) -> None:
        """Test __repr__."""
        ff = FeatureFlags((FakeLogin,), {})
        compat = FeatureFlagsCompat(ff)
        assert "FeatureFlagsCompat" in repr(compat)
        assert "FAKE_LOGIN" in repr(compat)

    def test_bool(self) -> None:
        """Test __bool__ delegation."""
        ff_off = FeatureFlags((FakeLogin,), {})
        assert not bool(FeatureFlagsCompat(ff_off))
        ff_on = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        assert bool(FeatureFlagsCompat(ff_on))

    def test_get_all(self) -> None:
        """Test get_all() delegation."""
        ff = FeatureFlags((FakeLogin,), {"FAKE_LOGIN": True})
        compat = FeatureFlagsCompat(ff)
        all_flags = compat.get_all()
        assert "FAKE_LOGIN" in all_flags
        assert all_flags["FAKE_LOGIN"]["value"] is True


class TestConfigWithFeatureFlags:
    """Tests for Config with FeatureFlags integration."""

    def test_default_feature_flags(self) -> None:
        """Test that feature_flags has a default FeatureFlags instance."""
        config = Config.parse_yaml("config-template.yml")
        assert isinstance(config.feature_flags, FeatureFlags)
        assert config.feature_flags[FakeLogin] is False

    def test_config_with_feature_flags_from_yaml(self) -> None:
        """Test that template config can be parsed with feature flags."""
        config = Config.parse_yaml("tests/unit_tests/test_data/config_with_flags.yml")
        assert config.feature_flags[FakeLogin] is True

    def test_config_model_validate_with_dict(self) -> None:
        """Test that Config.model_validate coerces FEATURE_FLAGS dict."""
        config_data = {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",
            "FEATURE_FLAGS": {"FAKE_LOGIN": True},
            "DB": {"TYPE": "json", "DATA": {}},
        }
        config = Config.model_validate(config_data)
        assert isinstance(config.feature_flags, FeatureFlags)
        assert config.feature_flags[FakeLogin] is True

    def test_config_feature_flags_eq_dict(self) -> None:
        """Test that config.feature_flags == dict works."""
        config_data = {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",
            "FEATURE_FLAGS": {"FAKE_LOGIN": True},
            "DB": {"TYPE": "json", "DATA": {}},
        }
        config = Config.model_validate(config_data)
        assert config.feature_flags == {"FAKE_LOGIN": True}

    def test_config_model_dump_serializes_feature_flags(self) -> None:
        """Test that model_dump serializes FeatureFlags to dict."""
        config_data = {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",
            "FEATURE_FLAGS": {"FAKE_LOGIN": True},
            "DB": {"TYPE": "json", "DATA": {}},
        }
        config = Config.model_validate(config_data)
        dumped = config.model_dump(by_alias=True)
        assert dumped["FEATURE_FLAGS"] == {"FAKE_LOGIN": True}


def test_parse_template_config() -> None:
    """Test that the template config can be parsed."""
    config = Config.parse_yaml("config-template.yml")
    langs_dict = languages_dict(config.languages)

    # languages_dict excludes None values
    wanted_dict = {
        "en": {"flag": "uk", "name": "English", "country": "GB"},
        "pl": {"flag": "pl", "name": "polski", "country": "PL"},
    }
    assert langs_dict == wanted_dict


def test_parse_non_existing_config_file() -> None:
    """Assure that parsing a non-existing config file raises an error and exits application."""
    with pytest.raises(SystemExit):
        Config.parse_yaml("non-existing-file.yml")
