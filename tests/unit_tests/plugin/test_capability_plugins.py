"""Tests for typed capability plugin base classes and engine routing."""

from __future__ import annotations

from typing import Any, cast
from unittest import mock

import jinja2.ext
import pytest

from platzky.attachment import AttachmentProtocol
from platzky.config import Config
from platzky.db.db import DB
from platzky.engine import Engine
from platzky.models import CmsModule
from platzky.notification_topics import NotificationTopic
from platzky.platzky import create_app_from_config, create_engine
from platzky.plugin.plugin import (
    CmsModuleBase,
    ContentFilterBase,
    LoginBase,
    NotifierBase,
    NotifierBaseConfig,
    PluginBase,
    PluginBaseConfig,
)
from platzky.shortcodes import Shortcode, apply_shortcodes

# ---------------------------------------------------------------------------
# Fixtures and helpers
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


def _app_with_plugin(base_config_data: dict[str, Any], name: str, plugin_class: type) -> Engine:
    """Load a single plugin via a mocked entry point and return the fully configured app."""
    base_config_data["DB"]["DATA"]["plugins"] = [{"name": name, "config": {}}]
    config = Config.model_validate(base_config_data)
    ep = mock.MagicMock()
    ep.name = name
    ep.load.return_value = plugin_class
    with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
        return create_app_from_config(config)


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

    def test_broadcast_topic_reaches_filtered_notifiers(self, app: Engine) -> None:
        """app.notify() default topic '*' must reach notifiers filtered to specific topics."""
        security_only = TopicFilteredNotifier({"accepted_topics": ["security"]})
        app.plugins[NotifierBase].append(security_only)

        app.notify("broadcast message")  # default topic is "*"

        assert len(security_only.received) == 1
        assert security_only.received[0][0] == "broadcast message"


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

    def test_login_base_registered_under_capability_key(
        self, base_config_data: dict[str, Any]
    ) -> None:
        app = _app_with_plugin(base_config_data, "google", GoogleLogin)
        assert any(isinstance(p, GoogleLogin) for p in app.get_plugins(LoginBase))

    def test_login_base_not_registered_under_notifier(
        self, base_config_data: dict[str, Any]
    ) -> None:
        app = _app_with_plugin(base_config_data, "google", GoogleLogin)
        assert not any(isinstance(p, GoogleLogin) for p in app.get_plugins(NotifierBase))


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

    def test_cms_module_registered_under_capability_key(
        self, base_config_data: dict[str, Any]
    ) -> None:
        app = _app_with_plugin(base_config_data, "gallery", GalleryCmsModule)
        assert any(isinstance(p, GalleryCmsModule) for p in app.get_plugins(CmsModuleBase))


# ---------------------------------------------------------------------------
# ContentFilterBase
# ---------------------------------------------------------------------------


class ShoutFilter(ContentFilterBase[PluginBaseConfig]):
    """Registers a [shout] shortcode that upper-cases its content."""

    @classmethod
    def get_config_model(cls) -> type[PluginBaseConfig]:
        return PluginBaseConfig

    def get_content_tags(self) -> dict[str, Shortcode]:
        return {
            "shout": Shortcode(
                name="shout",
                handler=lambda _attrs, content: content.upper(),
                description="Upper-case content.",
            )
        }


class TestContentFilterBase:
    def test_default_returns_empty_dict(self) -> None:
        class NoOpFilter(ContentFilterBase[PluginBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

        f = NoOpFilter({})
        assert f.get_content_tags() == {}

    def test_override_registers_shortcode(self) -> None:
        f = ShoutFilter({})
        tags = f.get_content_tags()
        assert "shout" in tags
        assert tags["shout"].handler({}, "hello") == "HELLO"

    def test_filters_registered_under_capability_key(
        self, base_config_data: dict[str, Any]
    ) -> None:
        app = _app_with_plugin(base_config_data, "shout", ShoutFilter)
        assert any(isinstance(p, ShoutFilter) for p in app.get_plugins(ContentFilterBase))

    def test_shortcodes_from_multiple_plugins_chainable(self) -> None:
        class AFilter(ContentFilterBase[PluginBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

            def get_content_tags(self) -> dict[str, Shortcode]:
                return {
                    "atag": Shortcode(
                        name="atag",
                        handler=lambda _attrs, content: f"A({content})",
                        description="wrap in A",
                    )
                }

        class BFilter(ContentFilterBase[PluginBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

            def get_content_tags(self) -> dict[str, Shortcode]:
                return {
                    "btag": Shortcode(
                        name="btag",
                        handler=lambda _attrs, content: f"B({content})",
                        description="wrap in B",
                    )
                }

        combined = {**AFilter({}).get_content_tags(), **BFilter({}).get_content_tags()}
        result = apply_shortcodes("[atag]x[/atag] [btag]y[/btag]", combined)
        assert result == "A(x) B(y)"


# ---------------------------------------------------------------------------
# Plugin capability registration
# ---------------------------------------------------------------------------


class TestRegisterPluginCapabilities:
    def test_uncategorised_plugin_stored_under_pluginbase(
        self, base_config_data: dict[str, Any]
    ) -> None:
        class GenericPlugin(PluginBase[PluginBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

        app = _app_with_plugin(base_config_data, "generic", GenericPlugin)
        assert any(isinstance(p, GenericPlugin) for p in app.get_plugins(PluginBase))
        assert not any(isinstance(p, GenericPlugin) for p in app.get_plugins(NotifierBase))

    def test_plugin_stored_under_concrete_type(self, base_config_data: dict[str, Any]) -> None:
        app = _app_with_plugin(base_config_data, "simple", SimpleNotifier)
        assert any(isinstance(p, SimpleNotifier) for p in app.get_plugins(SimpleNotifier))

    def test_multi_capability_plugin_registered_under_all_bases(
        self, base_config_data: dict[str, Any]
    ) -> None:
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
                pass  # intentionally empty — test only checks plugin registration

            def get_login_html(self) -> str:
                return ""

        app = _app_with_plugin(base_config_data, "multi", MultiPlugin)
        assert any(isinstance(p, MultiPlugin) for p in app.get_plugins(NotifierBase))
        assert any(isinstance(p, MultiPlugin) for p in app.get_plugins(LoginBase))

    def test_sub_plugins_not_registered_in_capability_buckets(
        self, base_config_data: dict[str, Any]
    ) -> None:
        class ParentPlugin(PluginBase[PluginBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

            def get_sub_plugins(self) -> list[PluginBase[Any]]:
                return [SimpleNotifier({})]

        app = _app_with_plugin(base_config_data, "parent", ParentPlugin)
        # The SimpleNotifier sub-plugin must NOT be auto-registered in capability buckets
        assert not any(isinstance(p, SimpleNotifier) for p in app.get_plugins(NotifierBase))


# ---------------------------------------------------------------------------
# Engine.all_plugins()
# ---------------------------------------------------------------------------


class TestAllPlugins:
    def test_all_plugins_empty_with_no_loaded_plugins(self, app: Engine) -> None:
        assert app.all_plugins() == []

    def test_all_plugins_includes_top_level(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        app.loaded_plugins.append(notifier)
        assert app.all_plugins() == [notifier]

    def test_all_plugins_includes_sub_plugins(self, app: Engine) -> None:
        sub = SimpleNotifier({})

        class ParentPlugin(PluginBase[PluginBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

            def get_sub_plugins(self) -> list[PluginBase[Any]]:
                return [sub]

        parent = ParentPlugin({})
        app.loaded_plugins.append(parent)

        assert app.all_plugins() == [parent, sub]

    def test_all_plugins_depth_first_nested(self, app: Engine) -> None:
        leaf = SimpleNotifier({})

        class MiddlePlugin(PluginBase[PluginBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

            def get_sub_plugins(self) -> list[PluginBase[Any]]:
                return [leaf]

        middle = MiddlePlugin({})

        class RootPlugin(PluginBase[PluginBaseConfig]):
            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

            def get_sub_plugins(self) -> list[PluginBase[Any]]:
                return [middle]

        root = RootPlugin({})
        app.loaded_plugins.append(root)

        assert app.all_plugins() == [root, middle, leaf]


# ---------------------------------------------------------------------------
# Backward compatibility: process() still called when overridden
# ---------------------------------------------------------------------------


class TestBackwardCompatProcess:
    def test_legacy_process_called_on_class_plugin(self, base_config_data: dict[str, Any]) -> None:
        class LegacyPlugin(PluginBase[PluginBaseConfig]):
            processed = False

            @classmethod
            def get_config_model(cls) -> type[PluginBaseConfig]:
                return PluginBaseConfig

            def process(self, app: Engine) -> Engine:
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
                pass  # intentionally empty — test only checks process() is not called

        base_config_data["DB"]["DATA"]["plugins"] = [{"name": "new", "config": {}}]
        config = Config.model_validate(base_config_data)

        with (
            mock.patch("platzky.plugin.plugin_loader.find_plugin"),
            mock.patch("platzky.plugin.plugin_loader._is_class_plugin", return_value=NewPlugin),
            mock.patch.object(PluginBase, "process", wraps=PluginBase.process) as mock_process,
        ):
            create_app_from_config(config)

        mock_process.assert_not_called()


# ---------------------------------------------------------------------------
# ContentFilterBase wiring in create_app_from_config
# ---------------------------------------------------------------------------


class ShoutTagPlugin(ContentFilterBase[PluginBaseConfig]):
    """Registers a [shout] shortcode via get_content_tags()."""

    @classmethod
    def get_config_model(cls) -> type[PluginBaseConfig]:
        return PluginBaseConfig

    def get_content_tags(self) -> dict[str, Shortcode]:
        return {
            "shout": Shortcode(
                name="shout",
                handler=lambda _attrs, content: content.upper(),
                description="Upper-case content.",
            )
        }


class _DummyJinjaExtension(jinja2.ext.Extension):
    tags = {"dummy_tag"}  # noqa: RUF012


class JinjaExtPlugin(ContentFilterBase[PluginBaseConfig]):
    """Test filter that exposes a Jinja2 extension."""

    @classmethod
    def get_config_model(cls) -> type[PluginBaseConfig]:
        return PluginBaseConfig

    def get_jinja_extensions(self) -> list[type[jinja2.ext.Extension]]:
        return [_DummyJinjaExtension]


class TestContentFilterWiring:
    def test_shortcode_registered_in_engine(self, base_config_data: dict[str, Any]) -> None:
        """Plugin shortcodes must appear in engine.shortcodes after app creation."""
        app = _app_with_plugin(base_config_data, "shout", ShoutTagPlugin)
        assert "shout" in app.shortcodes

    def test_shortcode_dispatched_via_content_filter(
        self, base_config_data: dict[str, Any]
    ) -> None:
        """Plugin shortcode must transform content passed through the blog blueprint."""
        app = _app_with_plugin(base_config_data, "shout", ShoutTagPlugin)
        assert any(isinstance(p, ShoutTagPlugin) for p in app.get_plugins(ContentFilterBase))
        result = apply_shortcodes("[shout]hello[/shout]", app.shortcodes)
        assert result == "HELLO"

    def test_jinja_extensions_registered(self, base_config_data: dict[str, Any]) -> None:
        """get_jinja_extensions() classes must appear in engine.jinja_env.extensions."""
        app = _app_with_plugin(base_config_data, "jinjaext", JinjaExtPlugin)
        assert any("_DummyJinjaExtension" in k for k in app.jinja_env.extensions)
