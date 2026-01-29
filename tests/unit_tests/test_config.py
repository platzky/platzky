import warnings

import pytest
from pydantic import ValidationError

from platzky.config import Config, FeatureFlagsConfig, languages_dict


class TestFeatureFlagsConfig:
    """Tests for FeatureFlagsConfig class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        flags = FeatureFlagsConfig()
        assert flags.fake_login is False

    def test_typed_flag_via_alias(self) -> None:
        """Test that typed flags can be set via alias."""
        flags = FeatureFlagsConfig.model_validate({"FAKE_LOGIN": True})
        assert flags.fake_login is True

    def test_typed_flag_via_name(self) -> None:
        """Test that typed flags can be set via field name."""
        flags = FeatureFlagsConfig.model_validate({"fake_login": True})
        assert flags.fake_login is True

    def test_get_typed_flag_by_alias(self) -> None:
        """Test .get() method returns typed flag value by alias."""
        flags = FeatureFlagsConfig.model_validate({"FAKE_LOGIN": True})
        assert flags.get("FAKE_LOGIN", False) is True

    def test_get_typed_flag_by_name(self) -> None:
        """Test .get() method returns typed flag value by field name."""
        flags = FeatureFlagsConfig.model_validate({"fake_login": True})
        assert flags.get("fake_login", False) is True

    def test_get_unknown_flag_returns_default(self) -> None:
        """Test .get() returns default for unknown flags."""
        flags = FeatureFlagsConfig()
        assert flags.get("UNKNOWN_FLAG", False) is False
        assert flags.get("UNKNOWN_FLAG", True) is True

    def test_untyped_flag_stored_in_extra(self) -> None:
        """Test that untyped flags are stored in model_extra."""
        flags = FeatureFlagsConfig.model_validate({"CUSTOM_FLAG": True})
        extra = flags.model_extra
        assert extra is not None
        assert "CUSTOM_FLAG" in extra
        assert extra["CUSTOM_FLAG"] is True

    def test_get_untyped_flag_emits_deprecation_warning(self) -> None:
        """Test .get() emits deprecation warning for untyped flags with migration example."""
        flags = FeatureFlagsConfig.model_validate({"CUSTOM_FLAG": True})

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = flags.get("CUSTOM_FLAG", False)

            assert result is True
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            warning_msg = str(w[0].message)
            assert "CUSTOM_FLAG" in warning_msg
            assert "2.0.0" in warning_msg
            # Check migration example is included
            assert "class MyFeatureFlags" in warning_msg
            assert "custom_flag: bool = Field" in warning_msg

    def test_get_typed_flag_no_warning(self) -> None:
        """Test .get() does not emit warning for typed flags."""
        flags = FeatureFlagsConfig.model_validate({"FAKE_LOGIN": True})

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = flags.get("FAKE_LOGIN", False)

            assert result is True
            assert len(w) == 0

    def test_frozen_config(self) -> None:
        """Test that the config is immutable."""
        flags = FeatureFlagsConfig()
        with pytest.raises(ValidationError):
            flags.fake_login = True


class TestConfigWithFeatureFlags:
    """Tests for Config with FeatureFlagsConfig integration."""

    def test_default_feature_flags(self) -> None:
        """Test that feature_flags has a default FeatureFlagsConfig instance."""
        config = Config.parse_yaml("config-template.yml")
        assert isinstance(config.feature_flags, FeatureFlagsConfig)
        assert config.feature_flags.fake_login is False

    def test_config_with_feature_flags_from_yaml(self) -> None:
        """Test that template config can be parsed with feature flags."""
        config = Config.parse_yaml("tests/unit_tests/test_data/config_with_flags.yml")
        assert config.feature_flags.fake_login is True


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
