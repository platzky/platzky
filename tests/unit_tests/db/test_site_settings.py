import pytest

from platzky.db.site_config_repository import SiteSettings
from platzky.models import Image

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


def test_key_missing_from_overrides_uses_the_default():
    settings = SiteSettings.from_layers(
        {"app_name": "Default", "app_title": "Title"}, {"app_name": "English"}, "en"
    )

    assert settings == SiteSettings(app_name="English", app_title="Title")


@pytest.mark.parametrize("empty", [None, ""], ids=["null", "empty"])
def test_empty_override_falls_through_to_the_default(empty: str | None):
    settings = SiteSettings.from_layers(
        {"app_name": "Default", "logo_url": "/logo.png"},
        {"app_name": empty, "logo_url": empty},
        "en",
    )

    assert settings == SiteSettings(app_name="Default", logo=Image(url="/logo.png"))


def test_localized_logo_overrides_the_default():
    settings = SiteSettings.from_layers({"logo_url": "/logo.png"}, {"logo_url": "/pl.png"}, "pl")

    assert settings.logo == Image(url="/pl.png")


@pytest.mark.parametrize("key", SiteSettings.STORED_KEYS)
def test_null_value_is_treated_as_unconfigured(key: str):
    assert SiteSettings.from_layers({key: None}, {key: None}, "en") == SiteSettings()


def test_legacy_description_dict_is_empty_for_a_missing_language():
    settings = SiteSettings.from_layers({"app_description": {"en": "Hi"}}, {}, "de")

    assert settings.app_description == ""


def test_localized_description_overrides_the_legacy_dict():
    settings = SiteSettings.from_layers(
        {"app_description": {"en": "Legacy"}}, {"app_description": "New"}, "en"
    )

    assert settings.app_description == "New"
