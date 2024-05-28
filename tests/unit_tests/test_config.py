from platzky.config import Config, languages_dict

import pytest

def test_parse_template_config() -> None:
    """Test that the template config can be parsed."""
    config = Config.parse_yaml("config-template.yml")
    langs_dict = languages_dict(config.languages)

def test_parse_template_config() -> None:
    """Test that the template config can be parsed."""
    config = Config.parse_yaml("config-template.yml")
    langs_dict = languages_dict(config.languages)
    assert langs_dict == wanted_dict
    wanted_dict = {
        "en": {"domain": None, "flag": "uk", "name": "English"},
        "pl": {"domain": None, "flag": "pl", "name": "polski"},
    }
    assert langs_dict == wanted_dict


def test_parse_non_existing_config_file() -> None:
    """Assure that parsing a non-existing config file raises an error and exits application."""
    with pytest.raises(SystemExit):
        Config.parse_yaml("non-existing-file.yml")
