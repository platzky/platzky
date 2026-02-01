import pytest

from platzky.config import Config, languages_dict
from platzky.feature_flags import FakeLogin, FeatureFlag, parse_flags, unregister
from platzky.feature_flags_wrapper import FeatureFlagSet


class TestFeatureFlag:
    """Tests for FeatureFlag construction and validation."""

    def test_valid_flag(self) -> None:
        """Test that a valid FeatureFlag can be created."""
        flag = FeatureFlag(
            alias="MY_FLAG", default=True, description="A test flag.", register=False
        )
        assert flag.alias == "MY_FLAG"
        assert flag.default is True
        assert flag.description == "A test flag."

    def test_empty_alias_raises(self) -> None:
        """Test that FeatureFlag with empty alias raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            FeatureFlag(alias="")

    def test_defaults(self) -> None:
        """Test that FeatureFlag has correct defaults."""
        flag = FeatureFlag(alias="MINIMAL", register=False)
        assert flag.default is False
        assert flag.description == ""

    def test_equality_by_alias(self) -> None:
        """Test that two flags with the same alias are equal."""
        a = FeatureFlag(alias="SAME", register=False)
        b = FeatureFlag(alias="SAME", register=False)
        assert a == b

    def test_hash_by_alias(self) -> None:
        """Test that two flags with the same alias have the same hash."""
        a = FeatureFlag(alias="SAME_HASH", register=False)
        b = FeatureFlag(alias="SAME_HASH", register=False)
        assert hash(a) == hash(b)


class TestParseFlags:
    """Tests for parse_flags standalone function."""

    def test_defaults_all_disabled(self) -> None:
        """Test parse_flags uses defaults when no raw_data."""
        result = parse_flags({})
        assert isinstance(result, frozenset)
        assert FakeLogin not in result

    def test_defaults_no_raw_data(self) -> None:
        """Test parse_flags with None raw_data."""
        result = parse_flags()
        assert isinstance(result, frozenset)
        assert FakeLogin not in result

    def test_enable_flag(self) -> None:
        """Test parse_flags picks up values from raw_data."""
        result = parse_flags({"FAKE_LOGIN": True})
        assert FakeLogin in result

    def test_disable_flag(self) -> None:
        """Test parse_flags with explicit False."""
        result = parse_flags({"FAKE_LOGIN": False})
        assert FakeLogin not in result

    def test_unknown_keys_ignored(self) -> None:
        """Test that unknown keys in raw_data are silently ignored."""
        result = parse_flags({"FAKE_LOGIN": True, "CUSTOM": True})
        assert FakeLogin in result

    def test_flag_with_default_true(self) -> None:
        """Test that a flag with default=True is enabled without raw_data."""
        default_on = FeatureFlag(alias="DEFAULT_ON", default=True)
        try:
            result = parse_flags()
            assert default_on in result
        finally:
            unregister(default_on)

    def test_result_is_frozenset(self) -> None:
        """Test that parse_flags returns a frozenset."""
        result = parse_flags({"FAKE_LOGIN": True})
        assert isinstance(result, frozenset)


class TestConfigWithFeatureFlags:
    """Tests for Config with feature flags integration."""

    def test_default_feature_flags(self) -> None:
        """Test that feature_flags defaults to a FeatureFlagSet instance."""
        config = Config.parse_yaml("config-template.yml")
        assert isinstance(config.feature_flags, FeatureFlagSet)
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
        assert isinstance(config.feature_flags, FeatureFlagSet)
        assert FakeLogin in config.feature_flags

    def test_unknown_keys_preserved(self) -> None:
        """Test that unknown YAML flag keys are preserved in dict layer."""
        config_data = {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",
            "FEATURE_FLAGS": {"FAKE_LOGIN": True, "UNKNOWN_FLAG": True},
            "DB": {"TYPE": "json", "DATA": {}},
        }
        config = Config.model_validate(config_data)
        assert FakeLogin in config.feature_flags
        assert config.feature_flags.get("UNKNOWN_FLAG") is True
        assert config.feature_flags.get("FAKE_LOGIN") is True


class TestFeatureFlagSet:
    """Tests for the FeatureFlagSet backward-compatible wrapper."""

    def test_dict_get_access(self) -> None:
        """Test that dict .get() works for raw keys."""
        flag_set = FeatureFlagSet(frozenset(), {"MY_KEY": True})
        assert flag_set.get("MY_KEY") is True
        assert flag_set.get("MISSING") is None

    def test_dict_bracket_access(self) -> None:
        """Test that dict bracket access works."""
        flag_set = FeatureFlagSet(frozenset(), {"MY_KEY": True})
        assert flag_set["MY_KEY"] is True

    def test_attribute_access(self) -> None:
        """Test Jinja2 dot-notation attribute access."""
        flag_set = FeatureFlagSet(frozenset(), {"MY_KEY": True, "OFF": False})
        assert flag_set.MY_KEY is True
        assert flag_set.OFF is False

    def test_attribute_access_missing_raises(self) -> None:
        """Test that missing attribute raises AttributeError."""
        flag_set = FeatureFlagSet(frozenset(), {})
        with pytest.raises(AttributeError, match="MISSING"):
            _ = flag_set.MISSING

    def test_feature_flag_membership(self) -> None:
        """Test that FeatureFlag 'in' check uses typed set."""
        flag = FeatureFlag(alias="TEST_MEMBER", register=False)
        flag_set = FeatureFlagSet(frozenset({flag}), {"TEST_MEMBER": True})
        assert flag in flag_set

    def test_feature_flag_not_member(self) -> None:
        """Test that absent FeatureFlag is not in the set."""
        flag = FeatureFlag(alias="NOT_THERE", register=False)
        flag_set = FeatureFlagSet(frozenset(), {"OTHER": True})
        assert flag not in flag_set

    def test_string_key_membership(self) -> None:
        """Test that string 'in' check uses dict layer."""
        flag_set = FeatureFlagSet(frozenset(), {"MY_KEY": True})
        assert "MY_KEY" in flag_set
        assert "MISSING" not in flag_set

    def test_enabled_flags_property(self) -> None:
        """Test the enabled_flags property returns the frozenset."""
        flag = FeatureFlag(alias="PROP_TEST", register=False)
        enabled = frozenset({flag})
        flag_set = FeatureFlagSet(enabled, {"PROP_TEST": True})
        assert flag_set.enabled_flags == enabled

    def test_dict_equality(self) -> None:
        """Test that FeatureFlagSet compares equal to an equivalent dict."""
        raw = {"KEY_A": True, "KEY_B": False}
        flag_set = FeatureFlagSet(frozenset(), raw)
        assert flag_set == {"KEY_A": True, "KEY_B": False}

    def test_immutable(self) -> None:
        """Test that FeatureFlagSet rejects all dict mutations."""
        flag_set = FeatureFlagSet(frozenset(), {"MY_KEY": True})
        with pytest.raises(TypeError, match="immutable"):
            flag_set["X"] = True
        with pytest.raises(TypeError, match="immutable"):
            del flag_set["MY_KEY"]
        with pytest.raises(TypeError, match="immutable"):
            flag_set.pop("MY_KEY")
        with pytest.raises(TypeError, match="immutable"):
            flag_set.update({"X": True})
        with pytest.raises(TypeError, match="immutable"):
            flag_set.clear()
        with pytest.raises(TypeError, match="immutable"):
            flag_set.setdefault("X", True)

    def test_tojson_serializable(self) -> None:
        """Test that FeatureFlagSet is JSON-serializable (dict subclass)."""
        import json

        raw = {"FLAG_A": True, "FLAG_B": False}
        flag_set = FeatureFlagSet(frozenset(), raw)
        result = json.dumps(flag_set)
        assert json.loads(result) == raw


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
