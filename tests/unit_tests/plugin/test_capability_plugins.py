"""Tests for typed capability plugin base classes and engine routing."""

from __future__ import annotations

from typing import Any, cast
from unittest import mock

import pytest

from platzky.attachment import AttachmentProtocol
from platzky.config import Config
from platzky.db.db import DB
from platzky.engine import Engine
from platzky.models import CmsModule
from platzky.notification_topics import NotificationTopic
from platzky.platzky import create_engine
from platzky.plugin.plugin import (
    CmsModuleBase,
    ContentFilterBase,
    LoginBase,
    NotifierBase,
    NotifierBaseConfig,
    PluginBase,
    PluginBaseConfig,
)
from platzky.plugin.plugin_loader import (
    _register_plugin_capabilities,  # type: ignore[reportPrivateUsage]
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_config_data() -> dict[str, Any]:
    return {
        "APP_NAME": "testApp",
        "SECRET_KEY": "secret",
        "USE_WWW": False,
        "BLOG_PREFIX": "/",
        "TRANSLATION_DIRECTORIES": [],
        "DB": {"TYPE": "json", "DATA": {"plugins": []}},
    }


def _make_db(config: Config) -> DB:
    from platzky.db.db_loader import get_db

    return get_db(config.db)


@pytest.fixture
def app(base_config_data: dict[str, Any]) -> Engine:
    config = Config.model_validate(base_config_data)
    return create_engine(config, _make_db(config))


# ---------------------------------------------------------------------------
# NotifierBase
# ---------------------------------------------------------------------------


class SimpleNotifier(NotifierBase[NotifierBaseConfig]):
    @classmethod
    def get_config_model(cls) -> type[NotifierBaseConfig]:
        return NotifierBaseConfig

    def notify(
        self,
        message: str,
        topic: NotificationTopic,
        attachments: list[AttachmentProtocol] | None = None,
    ) -> None:
        self.received.append((message, topic, attachments))

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.received: list[tuple[str, str, list[AttachmentProtocol] | None]] = []


class TopicFilteredNotifier(NotifierBase[NotifierBaseConfig]):
    @classmethod
    def get_config_model(cls) -> type[NotifierBaseConfig]:
        return NotifierBaseConfig

    def notify(
        self,
        message: str,
        topic: NotificationTopic,
        attachments: list[AttachmentProtocol] | None = None,  # noqa: ARG002
    ) -> None:
        self.received.append((message, topic))

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.received: list[tuple[str, str]] = []


class TestNotifierBase:
    def test_notifier_receives_wildcard_notifications(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        app.plugins[NotifierBase].append(notifier)

        app.notify("hello", topic="general")

        assert notifier.received == [("hello", "general", None)]

    def test_notifier_accepts_all_topics_by_default(self) -> None:
        notifier = SimpleNotifier({})
        assert notifier.accepts("security")
        assert notifier.accepts("content")
        assert notifier.accepts("general")
        assert notifier.accepts("*")

    def test_notifier_with_specific_topic_filter(self) -> None:
        notifier = TopicFilteredNotifier({"accepted_topics": ["security"]})
        assert notifier.accepts("security")
        assert not notifier.accepts("content")
        assert not notifier.accepts("general")

    def test_notifier_wildcard_topic_filter(self) -> None:
        notifier = SimpleNotifier({"accepted_topics": ["*"]})
        assert notifier.accepts("security")
        assert notifier.accepts("anything")

    def test_notify_routes_by_topic(self, app: Engine) -> None:
        security_only = TopicFilteredNotifier({"accepted_topics": ["security"]})
        all_topics = SimpleNotifier({})
        app.plugins[NotifierBase].extend([security_only, all_topics])

        app.notify("breach detected", topic="security")
        app.notify("new post", topic="content")

        assert len(security_only.received) == 1
        assert security_only.received[0][1] == "security"
        assert len(all_topics.received) == 2

    def test_notify_with_attachments_forwarded(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        app.plugins[NotifierBase].append(notifier)
        fake_attachment = object()

        app.notify("msg", topic="general", attachments=[fake_attachment])  # type: ignore[list-item]

        assert notifier.received[0][2] == [fake_attachment]

    def test_accepted_topics_list_coerced_to_set(self) -> None:
        notifier = SimpleNotifier({"accepted_topics": ["security", "content"]})
        config = cast(NotifierBaseConfig, notifier.config)
        assert isinstance(config.accepted_topics, set)
        assert config.accepted_topics == {"security", "content"}


# ---------------------------------------------------------------------------
# LoginBase
# ---------------------------------------------------------------------------


class GoogleLogin(LoginBase[PluginBaseConfig]):
    @classmethod
    def get_config_model(cls) -> type[PluginBaseConfig]:
        return PluginBaseConfig

    def get_login_html(self) -> str:
        return "<a>Login with Google</a>"


class TestLoginBase:
    def test_get_login_html_returns_string(self) -> None:
        plugin = GoogleLogin({})
        assert plugin.get_login_html() == "<a>Login with Google</a>"

    def test_login_base_registered_under_capability_key(self, app: Engine) -> None:
        plugin = GoogleLogin({})
        _register_plugin_capabilities(app, plugin, "google")
        assert plugin in app.get_plugins(LoginBase)

    def test_login_base_not_registered_under_notifier(self, app: Engine) -> None:
        plugin = GoogleLogin({})
        _register_plugin_capabilities(app, plugin, "google")
        assert plugin not in app.get_plugins(NotifierBase)


# ---------------------------------------------------------------------------
# CmsModuleBase
# ---------------------------------------------------------------------------


class GalleryCmsModule(CmsModuleBase[PluginBaseConfig]):
    @classmethod
    def get_config_model(cls) -> type[PluginBaseConfig]:
        return PluginBaseConfig

    def get_cms_module(self) -> CmsModule:
        return CmsModule(
            name="Gallery", description="Photo gallery", template="gallery.html", slug="gallery"
        )


class TestCmsModuleBase:
    def test_get_cms_module_returns_module(self) -> None:
        plugin = GalleryCmsModule({})
        module = plugin.get_cms_module()
        assert module.name == "Gallery"

    def test_cms_module_registered_under_capability_key(self, app: Engine) -> None:
        plugin = GalleryCmsModule({})
        _register_plugin_capabilities(app, plugin, "gallery")
        assert plugin in app.get_plugins(CmsModuleBase)


# ---------------------------------------------------------------------------
# ContentFilterBase
# ---------------------------------------------------------------------------


class UpperCaseFilter(ContentFilterBase[PluginBaseConfig]):
    @classmethod
    def get_config_model(cls) -> type[PluginBaseConfig]:
        return PluginBaseConfig

    def filter_content(self, content: str) -> str:
        return content.upper()


class PrefixFilter(ContentFilterBase[PluginBaseConfig]):
    @classmethod
    def get_config_model(cls) -> type[PluginBaseConfig]:
        return PluginBaseConfig

    def filter_content(self, content: str) -> str:
        return f"[PREFIX] {content}"


class TestContentFilterBase:
    def test_default_passthrough(self) -> None:
        class NoOpFilter(ContentFilterBase[PluginBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

        f = NoOpFilter({})
        assert f.filter_content("hello") == "hello"

    def test_override_transforms_content(self) -> None:
        f = UpperCaseFilter({})
        assert f.filter_content("hello") == "HELLO"

    def test_filters_registered_under_capability_key(self, app: Engine) -> None:
        f = UpperCaseFilter({})
        _register_plugin_capabilities(app, f, "upper")
        assert f in app.get_plugins(ContentFilterBase)

    def test_filters_chainable(self) -> None:
        filters = [PrefixFilter({}), UpperCaseFilter({})]
        content = "hello"
        for f in filters:
            content = f.filter_content(content)
        assert content == "[PREFIX] HELLO"


# ---------------------------------------------------------------------------
# _register_plugin_capabilities
# ---------------------------------------------------------------------------


class TestRegisterPluginCapabilities:
    def test_uncategorised_plugin_stored_under_pluginbase(self, app: Engine) -> None:
        class GenericPlugin(PluginBase[PluginBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

        plugin = GenericPlugin({})
        _register_plugin_capabilities(app, plugin, "generic")
        assert plugin in app.get_plugins(PluginBase)
        assert plugin not in app.get_plugins(NotifierBase)

    def test_plugin_stored_under_concrete_type(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        _register_plugin_capabilities(app, notifier, "simple")
        assert notifier in app.get_plugins(SimpleNotifier)

    def test_multi_capability_plugin_registered_under_all_bases(self, app: Engine) -> None:
        class MultiPlugin(NotifierBase[NotifierBaseConfig], LoginBase[NotifierBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[NotifierBaseConfig]:
                return NotifierBaseConfig

            def notify(
                self,
                message: str,
                topic: NotificationTopic,
                attachments: list[AttachmentProtocol] | None = None,
            ) -> None:
                pass

            def get_login_html(self) -> str:
                return ""

        plugin = MultiPlugin({})
        _register_plugin_capabilities(app, plugin, "multi")
        assert plugin in app.get_plugins(NotifierBase)
        assert plugin in app.get_plugins(LoginBase)


# ---------------------------------------------------------------------------
# Backward compatibility: process() still called when overridden
# ---------------------------------------------------------------------------


class TestBackwardCompatProcess:
    def test_legacy_process_called_on_class_plugin(self, base_config_data: dict[str, Any]) -> None:
        from platzky.engine import Engine as EngineType
        from platzky.platzky import create_app_from_config

        class LegacyPlugin(PluginBase[PluginBaseConfig]):
            processed = False

            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

            def process(self, app: EngineType) -> EngineType:
                LegacyPlugin.processed = True
                return app

        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "legacy", "config": {}}]
        config = Config.model_validate(base_config_data)

        with (
            mock.patch("platzky.plugin.plugin_loader.find_plugin"),
            mock.patch("platzky.plugin.plugin_loader._is_class_plugin", return_value=LegacyPlugin),
        ):
            create_app_from_config(config)

        assert LegacyPlugin.processed

    def test_new_capability_plugin_process_not_called(
        self, base_config_data: dict[str, Any]
    ) -> None:
        from platzky.platzky import create_app_from_config

        class NewPlugin(NotifierBase[NotifierBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[NotifierBaseConfig]:
                return NotifierBaseConfig

            def notify(
                self,
                message: str,
                topic: NotificationTopic,
                attachments: list[AttachmentProtocol] | None = None,
            ) -> None:
                pass

        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "new", "config": {}}]
        config = Config.model_validate(base_config_data)

        with (
            mock.patch("platzky.plugin.plugin_loader.find_plugin"),
            mock.patch("platzky.plugin.plugin_loader._is_class_plugin", return_value=NewPlugin),
            mock.patch.object(PluginBase, "process", wraps=PluginBase.process) as mock_process,
        ):
            create_app_from_config(config)

        mock_process.assert_not_called()
