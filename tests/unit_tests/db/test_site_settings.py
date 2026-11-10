from typing import Any

import pytest
from pydantic import ValidationError

from platzky.db.site_config_repository import LocalizedContent, SiteContent, SiteSettings
from platzky.models import Font, Image

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
    settings = SiteSettings.from_layers(
        SiteContent.model_validate({key: value}), LocalizedContent()
    )

    assert settings != SiteSettings()


def test_key_missing_from_overrides_uses_the_default():
    settings = SiteSettings.from_layers(
        SiteContent(app_name="Default", app_title="Title"), LocalizedContent(app_name="English")
    )

    assert settings == SiteSettings(app_name="English", app_title="Title")


def test_empty_override_falls_through_to_the_default():
    settings = SiteSettings.from_layers(
        SiteContent(app_name="Default", logo_url="/logo.png"),
        LocalizedContent(app_name="", logo_url=""),
    )

    assert settings == SiteSettings(app_name="Default", logo=Image(url="/logo.png"))


def test_global_values_are_not_overridden_by_a_language():
    settings = SiteSettings.from_layers(
        SiteContent(
            font=Font(name="Lora", url="https://fonts.googleapis.com/css2?family=Lora"),
            primary_color="blue",
        ),
        LocalizedContent(),
    )

    assert settings == SiteSettings(
        font=Font(name="Lora", url="https://fonts.googleapis.com/css2?family=Lora"),
        primary_color="blue",
    )


def test_localized_content_is_not_inherited_from_another_language():
    content = SiteContent.model_validate(
        {"localized_content": {"en": {"home_page_path": "/blog/page/about"}}}
    )

    assert content.localized("pl") == LocalizedContent()


@pytest.mark.parametrize("posts_key", ["posts", "pages"])
def test_sections_owned_by_the_blog_repository_are_accepted(posts_key: str):
    SiteContent.model_validate({posts_key: [{"title": "Anything"}]})


@pytest.mark.parametrize(
    "site_content",
    [
        {"menu_items": {"en": []}},
        {"blog_meta": {"en": {"title": "Notes"}}},
        {"footer": {"content": {"en": "Footer"}}},
        {"home_page_path": "/blog/page/about"},
        {"unknown": 1},
        {"localized_content": {"en": {"unknown": 1}}},
    ],
)
def test_unknown_keys_are_rejected(site_content: dict[str, Any]):
    with pytest.raises(ValidationError):
        SiteContent.model_validate(site_content)


@pytest.mark.parametrize(
    "site_content",
    [
        {"app_name": None},
        {"localized_content": None},
        {"localized_content": {"pl": None}},
        {"localized_content": {"pl": {"app_name": None}}},
        {"localized_content": {"pl": {"footer": None}}},
        {"localized_content": {"pl": {"blog_meta": None}}},
        {"localized_content": {"pl": {"menu_items": None}}},
        {"localized_content": {"pl": {"home_page_path": None}}},
    ],
)
def test_null_is_rejected(site_content: dict[str, Any]):
    with pytest.raises(ValidationError):
        SiteContent.model_validate(site_content)


def test_site_content_is_immutable():
    content = SiteContent.model_validate({"localized_content": {"en": {}}})

    with pytest.raises(ValidationError):
        content.app_name = "Changed"
    with pytest.raises(TypeError):
        content.localized_content["pl"] = LocalizedContent()  # type: ignore[index]
