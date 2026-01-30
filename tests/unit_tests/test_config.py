import pytest

from platzky.config import Config, languages_dict
from platzky.feature_flags import (
    FakeLogin,
    Flag,
    flags_to_dict,
    get_all_flags_metadata,
    parse_flags,
)


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


class TestParseFlags:
    """Tests for parse_flags standalone function."""

    def test_defaults_all_disabled(self) -> None:
        """Test parse_flags uses defaults when no raw_data."""
        result = parse_flags((FakeLogin,), {})
        assert isinstance(result, frozenset)
        assert FakeLogin not in result

    def test_defaults_no_raw_data(self) -> None:
        """Test parse_flags with None raw_data."""
        result = parse_flags((FakeLogin,))
        assert isinstance(result, frozenset)
        assert FakeLogin not in result

    def test_enable_flag(self) -> None:
        """Test parse_flags picks up values from raw_data."""
        result = parse_flags((FakeLogin,), {"FAKE_LOGIN": True})
        assert FakeLogin in result

    def test_disable_flag(self) -> None:
        """Test parse_flags with explicit False."""
        result = parse_flags((FakeLogin,), {"FAKE_LOGIN": False})
        assert FakeLogin not in result

    def test_unknown_keys_ignored(self) -> None:
        """Test that unknown keys in raw_data are silently ignored."""
        result = parse_flags((FakeLogin,), {"FAKE_LOGIN": True, "CUSTOM": True})
        assert FakeLogin in result
        # CUSTOM is not a registered flag type — it's just ignored
        assert len(result) == 1

    def test_flag_with_default_true(self) -> None:
        """Test that a flag with default=True is enabled without raw_data."""

        class DefaultOn(Flag):
            alias = "DEFAULT_ON"
            default = True

        result = parse_flags((DefaultOn,))
        assert DefaultOn in result

    def test_result_is_frozenset(self) -> None:
        """Test that parse_flags returns a frozenset."""
        result = parse_flags((FakeLogin,), {"FAKE_LOGIN": True})
        assert isinstance(result, frozenset)


class TestFlagsToDict:
    """Tests for flags_to_dict standalone function."""

    def test_enabled_flag(self) -> None:
        """Test flags_to_dict with enabled flag."""
        enabled = frozenset({FakeLogin})
        d = flags_to_dict(enabled, (FakeLogin,))
        assert d == {"FAKE_LOGIN": True}

    def test_disabled_flag(self) -> None:
        """Test flags_to_dict with disabled flag."""
        enabled: frozenset[type[Flag]] = frozenset()
        d = flags_to_dict(enabled, (FakeLogin,))
        assert d == {"FAKE_LOGIN": False}

    def test_multiple_flags(self) -> None:
        """Test flags_to_dict with multiple flags."""

        class Extra(Flag):
            alias = "EXTRA"

        enabled = frozenset({FakeLogin})
        d = flags_to_dict(enabled, (FakeLogin, Extra))
        assert d == {"FAKE_LOGIN": True, "EXTRA": False}


class TestGetAllFlagsMetadata:
    """Tests for get_all_flags_metadata standalone function."""

    def test_metadata_structure(self) -> None:
        """Test get_all_flags_metadata returns correct metadata."""
        enabled = frozenset({FakeLogin})
        all_flags = get_all_flags_metadata(enabled, (FakeLogin,))

        assert "FAKE_LOGIN" in all_flags
        assert all_flags["FAKE_LOGIN"]["value"] is True
        assert all_flags["FAKE_LOGIN"]["alias"] == "FAKE_LOGIN"
        assert all_flags["FAKE_LOGIN"]["default"] is False
        assert isinstance(all_flags["FAKE_LOGIN"]["description"], str)

    def test_disabled_flag_metadata(self) -> None:
        """Test get_all_flags_metadata with disabled flag."""
        enabled: frozenset[type[Flag]] = frozenset()
        all_flags = get_all_flags_metadata(enabled, (FakeLogin,))

        assert all_flags["FAKE_LOGIN"]["value"] is False


class TestPydanticIntegration:
    """Tests for Pydantic integration with EnabledFlags type."""

    def test_pydantic_core_schema_passthrough(self) -> None:
        """Test that Pydantic passes through frozenset instances."""
        from pydantic import BaseModel, ConfigDict, Field

        from platzky.feature_flags import EnabledFlags

        class TestModel(BaseModel):
            model_config = ConfigDict(frozen=True)
            flags: EnabledFlags = Field(default_factory=frozenset)

        ff = frozenset({FakeLogin})
        m = TestModel(flags=ff)
        assert m.flags is ff
        assert FakeLogin in m.flags

    def test_pydantic_core_schema_dict_coercion(self) -> None:
        """Test that Pydantic coerces dicts to frozenset."""
        from pydantic import BaseModel, ConfigDict, Field

        from platzky.feature_flags import EnabledFlags

        class TestModel(BaseModel):
            model_config = ConfigDict(frozen=True)
            flags: EnabledFlags = Field(default_factory=frozenset)

        m = TestModel(flags={"FAKE_LOGIN": True})  # type: ignore[arg-type]
        assert isinstance(m.flags, frozenset)
        assert FakeLogin in m.flags

    def test_pydantic_core_schema_serialization(self) -> None:
        """Test that Pydantic serializes via flags_to_dict."""
        from pydantic import BaseModel, ConfigDict, Field

        from platzky.feature_flags import EnabledFlags

        class TestModel(BaseModel):
            model_config = ConfigDict(frozen=True)
            flags: EnabledFlags = Field(default_factory=frozenset)

        ff = frozenset({FakeLogin})
        m = TestModel(flags=ff)
        dumped = m.model_dump()
        assert dumped["flags"] == {"FAKE_LOGIN": True}


class TestConfigWithFeatureFlags:
    """Tests for Config with feature flags integration."""

    def test_default_feature_flags(self) -> None:
        """Test that feature_flags has a default frozenset instance."""
        config = Config.parse_yaml("config-template.yml")
        assert isinstance(config.feature_flags, frozenset)
        assert FakeLogin not in config.feature_flags

    def test_config_with_feature_flags_from_yaml(self) -> None:
        """Test that template config can be parsed with feature flags."""
        config = Config.parse_yaml("tests/unit_tests/test_data/config_with_flags.yml")
        assert FakeLogin in config.feature_flags

    def test_config_model_validate_with_dict(self) -> None:
        """Test that Config.model_validate coerces FEATURE_FLAGS dict."""
        config_data = {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",
            "FEATURE_FLAGS": {"FAKE_LOGIN": True},
            "DB": {"TYPE": "json", "DATA": {}},
        }
        config = Config.model_validate(config_data)
        assert isinstance(config.feature_flags, frozenset)
        assert FakeLogin in config.feature_flags

    def test_config_model_dump_serializes_feature_flags(self) -> None:
        """Test that model_dump serializes feature flags to dict."""
        config_data = {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",
            "FEATURE_FLAGS": {"FAKE_LOGIN": True},
            "DB": {"TYPE": "json", "DATA": {}},
        }
        config = Config.model_validate(config_data)
        dumped = config.model_dump(by_alias=True)
        assert dumped["FEATURE_FLAGS"] == {"FAKE_LOGIN": True}

    def test_config_unknown_flags_ignored(self) -> None:
        """Test that unknown YAML flag keys are silently ignored."""
        config_data = {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",
            "FEATURE_FLAGS": {"FAKE_LOGIN": True, "UNKNOWN_FLAG": True},
            "DB": {"TYPE": "json", "DATA": {}},
        }
        config = Config.model_validate(config_data)
        assert FakeLogin in config.feature_flags
        # Unknown flags are simply ignored, only registered flags matter
        assert len(config.feature_flags) == 1


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
