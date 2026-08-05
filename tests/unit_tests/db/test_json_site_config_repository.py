from platzky.db.json_site_config_repository import JsonSiteConfigRepository


class TestJsonSiteConfigRepository:
    def test_get_site_settings(self):
        repository = JsonSiteConfigRepository(
            {
                "site_content": {
                    "logo_url": "/logo.png",
                    "favicon_url": "/favicon.ico",
                    "font": "Arial",
                    "primary_color": "blue",
                    "secondary_color": "green",
                    "app_description": {"en": "Hello", "pl": "Cześć"},
                }
            }
        )

        settings = repository.get_site_settings()

        assert settings.logo is not None
        assert settings.logo.url == "/logo.png"
        assert settings.favicon_url == "/favicon.ico"
        assert settings.font == "Arial"
        assert settings.primary_color == "blue"
        assert settings.secondary_color == "green"
        assert settings.app_description == {"en": "Hello", "pl": "Cześć"}

    def test_get_site_settings_defaults(self):
        repository = JsonSiteConfigRepository({"site_content": {}})

        settings = repository.get_site_settings()

        assert settings.logo is None
        assert settings.favicon_url == ""
        assert settings.font == ""
        assert settings.primary_color == "white"
        assert settings.secondary_color == "navy"
        assert settings.app_description == {}

    def test_get_menu_items_in_lang(self):
        repository = JsonSiteConfigRepository(
            {
                "site_content": {
                    "menu_items": {"en": [{"name": "Home", "url": "/"}]},
                }
            }
        )

        menu_items = repository.get_menu_items_in_lang("en")

        assert len(menu_items) == 1
        assert menu_items[0].name == "Home"

    def test_get_menu_items_in_lang_missing(self):
        repository = JsonSiteConfigRepository({"site_content": {}})
        assert repository.get_menu_items_in_lang("en") == []

    def test_get_home_page_path(self):
        repository = JsonSiteConfigRepository(
            {"site_content": {"home_page_path": "/blog/page/about"}}
        )
        assert repository.get_home_page_path("en") == "/blog/page/about"

    def test_get_home_page_path_per_locale(self):
        repository = JsonSiteConfigRepository(
            {
                "site_content": {
                    "home_page_path": {"en": "/en/about", "default": "/about"},
                }
            }
        )
        assert repository.get_home_page_path("en") == "/en/about"
        assert repository.get_home_page_path("pl") == "/about"

    def test_get_home_page_path_default(self):
        repository = JsonSiteConfigRepository({"site_content": {}})
        assert repository.get_home_page_path("en") is None
