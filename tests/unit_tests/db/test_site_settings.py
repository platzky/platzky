import pytest

from platzky.db.site_config_repository import SiteSettings

_NON_DEFAULTS = {
    "app_name": "Name",
    "app_title": "Title",
    "app_description": "Description",
    "logo_url": "/logo.png",
    "favicon_url": "/favicon.ico",
    "font": "Arial",
    "primary_color": "blue",
    "secondary_color": "green",
}


@pytest.mark.parametrize("key", SiteSettings.STORED_KEYS)
def test_every_stored_key_is_reflected_in_the_settings(key: str):
    settings = SiteSettings.from_layers({key: _NON_DEFAULTS[key]}, {}, "en")

    assert settings != SiteSettings()


def test_localized_text_overrides_defaults():
    settings = SiteSettings.from_layers({"app_name": "Default"}, {"app_name": "English"}, "en")

    assert settings.app_name == "English"


def test_legacy_description_dict_is_resolved_for_the_language():
    settings = SiteSettings.from_layers({"app_description": {"en": "Hi", "pl": "Cześć"}}, {}, "pl")

    assert settings.app_description == "Cześć"
