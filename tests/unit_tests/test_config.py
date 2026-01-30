import pytest

from platzky.config import Config, languages_dict
from platzky.feature_flags import FakeLogin, FeatureFlag, parse_flags


class TestFlagSubclass:
    """Tests for FeatureFlag.__init_subclass__ validation."""

    def test_valid_flag(self) -> None:
        """Test that a valid FeatureFlag subclass can be created."""

        class MyFlag(FeatureFlag):
            alias = "MY_FLAG"
            default = True
            description = "A test flag."

        assert MyFlag.alias == "MY_FLAG"
        assert MyFlag.default is True
        assert MyFlag.description == "A test flag."

    def test_flag_without_alias_raises(self) -> None:
        """Test that FeatureFlag subclass without alias raises TypeError."""
        with pytest.raises(TypeError, match="must define a non-empty 'alias'"):

            class BadFlag(FeatureFlag):
                pass

    def test_flag_with_empty_alias_raises(self) -> None:
        """Test that FeatureFlag subclass with empty alias raises TypeError."""
        with pytest.raises(TypeError, match="must define a non-empty 'alias'"):

            class BadFlag(FeatureFlag):
                alias = ""

    def test_flag_defaults(self) -> None:
        """Test that FeatureFlag subclass inherits defaults."""

        class MinimalFlag(FeatureFlag):
            alias = "MINIMAL"

        assert MinimalFlag.default is False
        assert MinimalFlag.description == ""


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

        class DefaultOn(FeatureFlag):
            alias = "DEFAULT_ON"
            default = True

        result = parse_flags()
        assert DefaultOn in result

    def test_result_is_frozenset(self) -> None:
        """Test that parse_flags returns a frozenset."""
        result = parse_flags({"FAKE_LOGIN": True})
        assert isinstance(result, frozenset)


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
