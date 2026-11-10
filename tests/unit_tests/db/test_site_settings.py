import pytest
from pydantic import ValidationError

from platzky.db.site_config_repository import (
    LocalizedContent,
    SiteConfig,
    SiteSettings,
)
from platzky.models import Font

_NON_DEFAULTS = {
    "app_name": "Name",
    "app_title": "Title",
    "app_description": "Description",
    "logo_url": "/logo.png",
    "favicon_url": "/favicon.ico",
    "font": {"name": "Lora", "url": "https://fonts.googleapis.com/css2?family=Lora"},
    "primary_color": "blue",
    "secondary_color": "green",
}


@pytest.mark.parametrize("key, value", _NON_DEFAULTS.items())
def test_every_stored_key_is_reflected_in_the_settings(key: str, value: object):
    settings = SiteSettings.from_layers(SiteConfig.model_validate({key: value}), LocalizedContent())

    assert settings != SiteSettings()


def test_key_missing_from_overrides_uses_the_default():
    settings = SiteSettings.from_layers(
        SiteConfig(app_name="Default", app_title="Title"), LocalizedContent(app_name="English")
    )

    assert settings == SiteSettings(app_name="English", app_title="Title")


def test_empty_override_falls_through_to_the_default():
    settings = SiteSettings.from_layers(
        SiteConfig(app_name="Default", logo_url="/logo.png"),
        LocalizedContent(app_name="", logo_url=""),
    )

    assert settings == SiteSettings(app_name="Default", logo_url="/logo.png")


def test_global_values_are_not_overridden_by_a_language():
    settings = SiteSettings.from_layers(
        SiteConfig(
            font=Font(name="Lora", url="https://fonts.googleapis.com/css2?family=Lora"),
            primary_color="blue",
        ),
        LocalizedContent(),
    )

    assert settings == SiteSettings(
        font=Font(name="Lora", url="https://fonts.googleapis.com/css2?family=Lora"),
        primary_color="blue",
    )


@pytest.mark.parametrize("key", ["primary_color", "secondary_color"])
def test_empty_colour_is_rejected(key: str):
    with pytest.raises(ValidationError, match=key):
        SiteConfig.model_validate({key: ""})
