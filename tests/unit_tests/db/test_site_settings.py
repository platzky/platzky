from typing import Any

import pytest
from pydantic import ValidationError

from platzky.db.site_config_repository import LocalizedContent, SiteContent, SiteSettings
from platzky.models import Footer, Image, MenuItem, PageMeta

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
    settings = SiteSettings.from_layers(
        SiteContent.model_validate({key: _NON_DEFAULTS[key]}), LocalizedContent()
    )

    assert settings != SiteSettings()


def test_localized_text_overrides_defaults():
    settings = SiteSettings.from_layers(
        SiteContent(app_name="Default"), LocalizedContent(app_name="English")
    )

    assert settings.app_name == "English"


def test_key_missing_from_overrides_uses_the_default():
    settings = SiteSettings.from_layers(
        SiteContent(app_name="Default", app_title="Title"), LocalizedContent(app_name="English")
    )

    assert settings == SiteSettings(app_name="English", app_title="Title")


@pytest.mark.parametrize("empty", [None, ""], ids=["null", "empty"])
def test_empty_override_falls_through_to_the_default(empty: str | None):
    settings = SiteSettings.from_layers(
        SiteContent(app_name="Default", logo_url="/logo.png"),
        LocalizedContent(app_name=empty, logo_url=empty),
    )

    assert settings == SiteSettings(app_name="Default", logo=Image(url="/logo.png"))


def test_localized_logo_overrides_the_default():
    settings = SiteSettings.from_layers(
        SiteContent(logo_url="/logo.png"), LocalizedContent(logo_url="/pl.png")
    )

    assert settings.logo == Image(url="/pl.png")


@pytest.mark.parametrize("key", SiteSettings.STORED_KEYS)
def test_null_value_is_treated_as_unconfigured(key: str):
    settings = SiteSettings.from_layers(
        SiteContent.model_validate({key: None}), LocalizedContent.model_validate({key: None})
    )

    assert settings == SiteSettings()


def test_global_values_are_not_overridden_by_a_language():
    settings = SiteSettings.from_layers(
        SiteContent(font="Arial", primary_color="blue"), LocalizedContent()
    )

    assert settings == SiteSettings(font="Arial", primary_color="blue")


def test_site_content_parses_the_documented_shape():
    content = SiteContent.model_validate(
        {
            "app_name": "Literature",
            "localized_content": {
                "pl": {
                    "blog_meta": {"title": "Notatki"},
                    "footer": {"content": "Stopka", "collapsible": True},
                    "menu_items": [{"name": "Start", "url": "/"}],
                    "home_page_path": "/blog/page/o-nas",
                }
            },
        }
    )

    assert content.localized("pl") == LocalizedContent(
        blog_meta=PageMeta(title="Notatki"),
        footer=Footer(content="Stopka", collapsible=True),
        menu_items=(MenuItem(name="Start", url="/"),),
        home_page_path="/blog/page/o-nas",
    )


def test_language_without_content_is_empty():
    assert SiteContent().localized("de") == LocalizedContent()


def test_localized_content_is_not_inherited_from_another_language():
    content = SiteContent.model_validate(
        {"localized_content": {"en": {"home_page_path": "/blog/page/about"}}}
    )

    assert content.localized("pl").home_page_path is None


def test_null_per_language_sections_are_unconfigured():
    content = LocalizedContent.model_validate(
        {"blog_meta": None, "footer": None, "menu_items": None, "home_page_path": None}
    )

    assert content == LocalizedContent()


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


def test_site_content_is_immutable():
    content = SiteContent.model_validate({"localized_content": {"en": {}}})

    with pytest.raises(ValidationError):
        content.app_name = "Changed"
    with pytest.raises(TypeError):
        content.localized_content["pl"] = LocalizedContent()  # type: ignore[index]
