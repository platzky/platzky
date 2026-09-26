from pathlib import Path

import pytest
from pydantic import ValidationError

from platzky.config import Config, languages_dict
from platzky.feature_flags import FakeLogin, FeatureFlag
from platzky.feature_flags_wrapper import FeatureFlagSet

_SCAFFOLD_CONFIG_FILE = "platzky/scaffold/config.template.yml"


class TestFeatureFlag:
    """Tests for FeatureFlag construction and validation."""

    def test_valid_flag(self) -> None:
        """Test that a valid FeatureFlag can be created."""
        flag = FeatureFlag(alias="MY_FLAG", default=True, description="A test flag.")
        assert flag.alias == "MY_FLAG"
        assert flag.default is True
        assert flag.description == "A test flag."

    def test_empty_alias_raises(self) -> None:
        """Test that FeatureFlag with empty alias raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            FeatureFlag(alias="")

    def test_defaults(self) -> None:
        """Test that FeatureFlag has correct defaults."""
        flag = FeatureFlag(alias="MINIMAL")
        assert flag.default is False
        assert flag.description == ""

    def test_equality_by_alias(self) -> None:
        """Test that two flags with the same alias are equal."""
        a = FeatureFlag(alias="SAME")
        b = FeatureFlag(alias="SAME")
        assert a == b

    def test_hash_by_alias(self) -> None:
        """Test that two flags with the same alias have the same hash."""
        a = FeatureFlag(alias="SAME_HASH")
        b = FeatureFlag(alias="SAME_HASH")
        assert hash(a) == hash(b)


class TestFlagResolution:
    """Tests for dynamic flag resolution via FeatureFlagSet.__contains__."""

    def test_defaults_all_disabled(self) -> None:
        """Test that a flag with default=False is not enabled in empty set."""
        flag_set = FeatureFlagSet({})
        assert FakeLogin not in flag_set

    def test_enable_flag(self) -> None:
        """Test that a flag is enabled when raw_data has it True."""
        flag_set = FeatureFlagSet({"FAKE_LOGIN": True})
        assert FakeLogin in flag_set

    def test_disable_flag(self) -> None:
        """Test that a flag is disabled when raw_data has it False."""
        flag_set = FeatureFlagSet({"FAKE_LOGIN": False})
        assert FakeLogin not in flag_set

    def test_unknown_keys_ignored(self) -> None:
        """Test that unknown keys in raw_data don't break anything."""
        flag_set = FeatureFlagSet({"FAKE_LOGIN": True, "CUSTOM": True})
        assert FakeLogin in flag_set

    def test_flag_with_default_true(self) -> None:
        """Test that a flag with default=True is enabled without raw_data."""
        default_on = FeatureFlag(alias="DEFAULT_ON", default=True)
        flag_set = FeatureFlagSet({})
        assert default_on in flag_set

    def test_flag_with_default_true_overridden(self) -> None:
        """Test that a flag with default=True can be disabled via raw_data."""
        default_on = FeatureFlag(alias="DEFAULT_ON", default=True)
        flag_set = FeatureFlagSet({"DEFAULT_ON": False})
        assert default_on not in flag_set


class TestConfigWithFeatureFlags:
    """Tests for Config with feature flags integration."""

    def test_default_feature_flags(self) -> None:
        """Test that feature_flags defaults to a FeatureFlagSet instance."""
        config = Config.parse_yaml(_SCAFFOLD_CONFIG_FILE)
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


class TestBlogPrefix:
    """Tests for the blog_prefix field and its validation."""

    def test_default_blog_prefix(self) -> None:
        """Test that blog_prefix defaults to /blog."""
        config_data = {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",
            "DB": {"TYPE": "json", "DATA": {}},
        }
        config = Config.model_validate(config_data)
        assert config.blog_prefix == "/blog"

    def test_root_blog_prefix_rejected(self) -> None:
        """Test that BLOG_PREFIX="/" is rejected, since "/" is reserved for the homepage route."""
        config_data = {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",
            "BLOG_PREFIX": "/",
            "DB": {"TYPE": "json", "DATA": {}},
        }
        with pytest.raises(ValidationError, match="BLOG_PREFIX"):
            Config.model_validate(config_data)

    def test_custom_blog_prefix_accepted(self) -> None:
        """Test that a non-root BLOG_PREFIX is accepted as-is."""
        config_data = {
            "APP_NAME": "test",
            "SECRET_KEY": "secret",
            "BLOG_PREFIX": "/articles",
            "DB": {"TYPE": "json", "DATA": {}},
        }
        config = Config.model_validate(config_data)
        assert config.blog_prefix == "/articles"


_EN = {"name": "English", "flag": "gb", "country": "GB"}
_PL = {"name": "polski", "flag": "pl", "country": "PL"}
_DE = {"name": "Deutsch", "flag": "de", "country": "DE"}


def _config_data(**overrides: object) -> dict[str, object]:
    return {
        "APP_NAME": "test",
        "SECRET_KEY": "secret",
        "DB": {"TYPE": "json", "DATA": {}},
        **overrides,
    }


class TestLanguages:
    """Tests for DEFAULT_LANGUAGE and the URL each language is served at."""

    def test_default_language_is_the_first_of_several_languages(self) -> None:
        config = Config.model_validate(_config_data(LANGUAGES={"pl": _PL, "de": _DE}))
        assert config.default_language == "pl"

    def test_default_language_is_the_first_even_when_en_is_configured(self) -> None:
        config = Config.model_validate(_config_data(LANGUAGES={"pl": _PL, "en": _EN}))
        assert config.default_language == "pl"

    def test_default_language_is_implied_with_one_language(self) -> None:
        config = Config.model_validate(_config_data(LANGUAGES={"pl": _PL}))
        assert config.default_language == "pl"

    def test_default_language_is_en_without_languages(self) -> None:
        assert Config.model_validate(_config_data()).default_language == "en"

    def test_default_language_must_be_configured(self) -> None:
        data = _config_data(DEFAULT_LANGUAGE="de", LANGUAGES={"en": _EN, "pl": _PL})
        with pytest.raises(ValidationError, match="not one of the configured LANGUAGES"):
            Config.model_validate(data)

    def test_domain_must_be_lowercase(self) -> None:
        languages = {"en": {**_EN, "domain": "Example.com"}}
        data = _config_data(DEFAULT_LANGUAGE="en", LANGUAGES=languages)
        with pytest.raises(ValidationError, match="must be lowercase"):
            Config.model_validate(data)

    def test_domains_must_be_unique(self) -> None:
        languages = {"en": {**_EN, "domain": "example.com"}, "pl": {**_PL, "domain": "example.com"}}
        data = _config_data(DEFAULT_LANGUAGE="en", LANGUAGES=languages)
        with pytest.raises(ValidationError, match="share the domain"):
            Config.model_validate(data)

    def test_default_language_needs_a_domain_when_another_has_one(self) -> None:
        languages = {"en": _EN, "pl": {**_PL, "domain": "example.pl"}}
        data = _config_data(DEFAULT_LANGUAGE="en", LANGUAGES=languages)
        with pytest.raises(ValidationError, match="needs a domain"):
            Config.model_validate(data)

    @pytest.mark.parametrize("lang_code", ["admin", "static", "lang", "blog", "pl pl", "pl/x"])
    def test_domainless_language_code_must_be_a_free_url_segment(self, lang_code: str) -> None:
        data = _config_data(DEFAULT_LANGUAGE="en", LANGUAGES={"en": _EN, lang_code: _PL})
        with pytest.raises(ValidationError, match="used as a URL segment"):
            Config.model_validate(data)

    @pytest.mark.parametrize("lang_code", ["api", "pl'x"])
    def test_language_code_with_a_domain_must_be_a_free_url_segment(self, lang_code: str) -> None:
        languages = {
            "en": {**_EN, "domain": "example.com"},
            lang_code: {**_PL, "domain": "example.pl"},
        }
        data = _config_data(DEFAULT_LANGUAGE="en", LANGUAGES=languages)
        with pytest.raises(ValidationError, match="used as a URL segment"):
            Config.model_validate(data)

    def test_domainless_language_code_must_not_collide_with_a_custom_blog_prefix(self) -> None:
        data = _config_data(
            BLOG_PREFIX="/articles",
            DEFAULT_LANGUAGE="en",
            LANGUAGES={"en": _EN, "articles": _PL},
        )
        with pytest.raises(ValidationError, match="used as a URL segment"):
            Config.model_validate(data)

    def test_domainless_languages_are_non_default_languages_without_a_domain(self) -> None:
        languages = {
            "en": {**_EN, "domain": "example.com"},
            "pl": _PL,
            "de": {**_DE, "domain": "example.de"},
            "uk": {"name": "Ukrainian", "flag": "ua", "country": "UA"},
        }
        config = Config.model_validate(_config_data(DEFAULT_LANGUAGE="en", LANGUAGES=languages))
        assert config.site_languages.domainless_languages == ("pl", "uk")


class TestFeatureFlagSet:
    """Tests for FeatureFlagSet."""

    def test_dict_get_access(self) -> None:
        """Test that dict .get() works for raw keys."""
        flag_set = FeatureFlagSet({"MY_KEY": True})
        assert flag_set.get("MY_KEY") is True
        assert flag_set.get("MISSING") is None

    def test_dict_bracket_access(self) -> None:
        """Test that dict bracket access works."""
        flag_set = FeatureFlagSet({"MY_KEY": True})
        assert flag_set["MY_KEY"] is True

    def test_feature_flag_membership(self) -> None:
        """Test that FeatureFlag 'in' check resolves dynamically."""
        flag = FeatureFlag(alias="TEST_MEMBER")
        flag_set = FeatureFlagSet({"TEST_MEMBER": True})
        assert flag in flag_set

    def test_feature_flag_not_member(self) -> None:
        """Test that absent FeatureFlag with default=False is not in the set."""
        flag = FeatureFlag(alias="NOT_THERE")
        flag_set = FeatureFlagSet({"OTHER": True})
        assert flag not in flag_set

    def test_string_key_membership(self) -> None:
        """Test that string 'in' check uses dict layer."""
        flag_set = FeatureFlagSet({"MY_KEY": True})
        assert "MY_KEY" in flag_set
        assert "MISSING" not in flag_set

    def test_dict_equality(self) -> None:
        """Test that FeatureFlagSet compares equal to an equivalent dict."""
        raw = {"KEY_A": True, "KEY_B": False}
        flag_set = FeatureFlagSet(raw)
        assert flag_set == {"KEY_A": True, "KEY_B": False}

    def test_immutable(self) -> None:
        """Test that FeatureFlagSet rejects all dict mutations."""
        flag_set = FeatureFlagSet({"MY_KEY": True})
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
        flag_set = FeatureFlagSet(raw)
        result = json.dumps(flag_set)
        assert json.loads(result) == raw


def test_parse_template_config() -> None:
    """Test that the template `platzky init` writes can be parsed."""
    config = Config.parse_yaml(_SCAFFOLD_CONFIG_FILE)
    langs_dict = languages_dict(config.languages)

    # languages_dict excludes None values
    assert langs_dict == {"en": {"flag": "uk", "name": "English", "country": "GB"}}


def test_parse_non_existing_config_file() -> None:
    """Assure that parsing a non-existing config file raises an error and exits application."""
    with pytest.raises(SystemExit):
        Config.parse_yaml("non-existing-file.yml")


def test_parse_invalid_yaml_config_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Assure that malformed YAML exits application with a clear message."""
    config_file = tmp_path / "config.yml"
    config_file.write_text("APP_NAME: [unclosed")

    with pytest.raises(SystemExit):
        Config.parse_yaml(str(config_file))

    assert "Invalid YAML in config file" in capsys.readouterr().err


def test_parse_unreadable_config_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Assure that a config path which cannot be read exits application with a clear message."""
    with pytest.raises(SystemExit):
        Config.parse_yaml(str(tmp_path))

    assert "Cannot read config file" in capsys.readouterr().err
