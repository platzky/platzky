"""Tests for typed capability plugin base classes and engine routing."""

from __future__ import annotations

from typing import Any
from unittest import mock

import jinja2.ext
import pytest

from platzky.attachment import AttachmentProtocol
from platzky.config import Config
from platzky.content_types import ALL_CONTENT_TYPES, ContentType
from platzky.db.db import DB
from platzky.engine import Engine
from platzky.notification_topics import NotificationTopic
from platzky.platzky import create_app_from_config, create_engine
from platzky.plugin.content_filter import ContentFilterBase
from platzky.plugin.notifier import NotifierBase
from platzky.plugin.plugin import PluginBase
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

_ALL_TOPICS: set[NotificationTopic] = {"general", "content", "security"}


class SimpleNotifier(NotifierBase):
    """Notifier that accepts all topics and records received messages."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_topics = set(config.get("accepted_topics", _ALL_TOPICS))
        self.received: list[tuple[str, str, list[AttachmentProtocol] | None]] = []

    def notify(
        self,
        message: str,
        topic: NotificationTopic,
        attachments: list[AttachmentProtocol] | None = None,
    ) -> None:
        self.received.append((message, topic, attachments))


class TopicFilteredNotifier(NotifierBase):
    """Notifier whose accepted_topics are configured via the config dict."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_topics = set(config.get("accepted_topics", set()))
        self.received: list[tuple[str, str]] = []

    def notify(
        self,
        message: str,
        topic: NotificationTopic,
        attachments: list[AttachmentProtocol] | None = None,  # noqa: ARG002
    ) -> None:
        self.received.append((message, topic))


class TestNotifierBase:
    def test_notifier_receives_matching_topic(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        app.plugins[NotifierBase].append(notifier)

        app.notify("hello", topic="general")

        assert notifier.received == [("hello", "general", None)]

    def test_notifier_only_receives_declared_topics(self, app: Engine) -> None:
        notifier = TopicFilteredNotifier({"accepted_topics": ["security"]})
        app.plugins[NotifierBase].append(notifier)

        app.notify("breach", topic="security")
        app.notify("new post", topic="content")
        app.notify("hi", topic="general")

        assert len(notifier.received) == 1
        assert notifier.received[0][1] == "security"

    def test_engine_allowlist_blocks_topic_plugin_wants(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        app.plugins[NotifierBase].append(notifier)
        app.set_notifier_allowlist(notifier, frozenset({"general"}))

        app.notify("breach", topic="security")
        app.notify("hi", topic="general")

        assert len(notifier.received) == 1
        assert notifier.received[0][1] == "general"

    def test_engine_allowlist_none_means_unrestricted(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        app.plugins[NotifierBase].append(notifier)
        app.set_notifier_allowlist(notifier, None)

        app.notify("breach", topic="security")
        app.notify("hi", topic="general")

        assert len(notifier.received) == 2

    def test_new_topic_not_received_without_explicit_opt_in(self, app: Engine) -> None:
        security_only = TopicFilteredNotifier({"accepted_topics": ["security"]})
        app.plugins[NotifierBase].append(security_only)

        app.notify("new topic message", topic="general")

        assert len(security_only.received) == 0

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

    def test_accepted_topics_from_config_list(self) -> None:
        notifier = TopicFilteredNotifier({"accepted_topics": ["security", "content"]})
        assert isinstance(notifier.accepted_topics, set)
        assert notifier.accepted_topics == {"security", "content"}


# ---------------------------------------------------------------------------
# ContentFilterBase
# ---------------------------------------------------------------------------


class ShoutFilter(ContentFilterBase):
    """Registers a [shout] shortcode that upper-cases its content."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_content_types: set[ContentType] = set(ALL_CONTENT_TYPES)

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
        class NoOpFilter(ContentFilterBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_content_types: set[ContentType] = set(ALL_CONTENT_TYPES)

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
        class AFilter(ContentFilterBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_content_types: set[ContentType] = set(ALL_CONTENT_TYPES)

            def get_content_tags(self) -> dict[str, Shortcode]:
                return {
                    "atag": Shortcode(
                        name="atag",
                        handler=lambda _attrs, content: f"A({content})",
                        description="wrap in A",
                    )
                }

        class BFilter(ContentFilterBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_content_types: set[ContentType] = set(ALL_CONTENT_TYPES)

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
        class GenericPlugin(PluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)

        app = _app_with_plugin(base_config_data, "generic", GenericPlugin)
        assert any(isinstance(p, GenericPlugin) for p in app.get_plugins(PluginBase))
        assert not any(isinstance(p, GenericPlugin) for p in app.get_plugins(NotifierBase))

    def test_plugin_stored_under_concrete_type(self, base_config_data: dict[str, Any]) -> None:
        app = _app_with_plugin(base_config_data, "simple", SimpleNotifier)
        assert any(isinstance(p, SimpleNotifier) for p in app.get_plugins(SimpleNotifier))

    def test_multi_capability_plugin_registered_under_all_bases(
        self, base_config_data: dict[str, Any]
    ) -> None:
        class MultiPlugin(NotifierBase, ContentFilterBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_topics: set[NotificationTopic] = {"general"}
                self.accepted_content_types: set[ContentType] = set(ALL_CONTENT_TYPES)

            def notify(
                self,
                message: str,
                topic: NotificationTopic,
                attachments: list[AttachmentProtocol] | None = None,
            ) -> None:
                # No-op: only verifies capability registration, not notification delivery.
                pass

        app = _app_with_plugin(base_config_data, "multi", MultiPlugin)
        assert any(isinstance(p, MultiPlugin) for p in app.get_plugins(NotifierBase))
        assert any(isinstance(p, MultiPlugin) for p in app.get_plugins(ContentFilterBase))


# ---------------------------------------------------------------------------
# PluginBase.get_info() and Engine.get_plugin_infos()
# ---------------------------------------------------------------------------


class TestGetInfo:
    def test_default_info_uses_class_name_and_docstring(self) -> None:
        class MyPlugin(PluginBase):
            """A plugin for testing."""

            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)

        info = MyPlugin({}).get_info()
        assert info.name == "MyPlugin"
        assert info.description == "A plugin for testing."

    def test_default_info_empty_description_when_no_docstring(self) -> None:
        class NoDocPlugin(PluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)

        assert NoDocPlugin({}).get_info().description == ""

    def test_get_plugin_infos_empty_with_no_loaded_plugins(self, app: Engine) -> None:
        assert app.get_plugin_infos() == []

    def test_get_plugin_infos_returns_info_for_each_loaded_plugin(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        app.loaded_plugins.append(notifier)
        infos = app.get_plugin_infos()
        assert len(infos) == 1
        assert infos[0].name == "SimpleNotifier"


# ---------------------------------------------------------------------------
# Backward compatibility: process() still called when overridden
# ---------------------------------------------------------------------------


class TestBackwardCompatProcess:
    def test_legacy_process_called_on_class_plugin(self, base_config_data: dict[str, Any]) -> None:
        class LegacyPlugin(PluginBase):
            processed = False

            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)

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
        class NewPlugin(NotifierBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_topics: set[NotificationTopic] = {"general"}

            def notify(
                self,
                message: str,
                topic: NotificationTopic,
                attachments: list[AttachmentProtocol] | None = None,
            ) -> None:
                # No-op: only verifies that process() is not called, not notification delivery.
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


# ---------------------------------------------------------------------------
# ContentFilterBase wiring in create_app_from_config
# ---------------------------------------------------------------------------


class ShoutTagPlugin(ContentFilterBase):
    """Registers a [shout] shortcode via get_content_tags()."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_content_types: set[ContentType] = set(ALL_CONTENT_TYPES)

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


class JinjaExtPlugin(ContentFilterBase):
    """Test filter that exposes a Jinja2 extension."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_content_types: set[ContentType] = set(ALL_CONTENT_TYPES)

    def get_jinja_extensions(self) -> list[type[jinja2.ext.Extension]]:
        return [_DummyJinjaExtension]


class TestContentFilterWiring:
    def test_shortcode_registered_in_engine(self, base_config_data: dict[str, Any]) -> None:
        """Plugin shortcodes must appear in engine.shortcodes after app creation."""
        app = _app_with_plugin(base_config_data, "shout", ShoutTagPlugin)
        assert "shout" in app.shortcodes

    def test_filter_content_applies_shortcode(self, base_config_data: dict[str, Any]) -> None:
        """filter_content() must transform content via the plugin's shortcode handler."""
        app = _app_with_plugin(base_config_data, "shout", ShoutTagPlugin)
        assert any(isinstance(p, ShoutTagPlugin) for p in app.get_plugins(ContentFilterBase))
        result = app.apply_content_filters("[shout]hello[/shout]", "post")
        assert result == "HELLO"

    def test_filter_only_applied_to_declared_content_type(
        self, base_config_data: dict[str, Any]
    ) -> None:
        """Plugins only receive content types listed in accepted_content_types."""

        class PostOnlyFilter(ContentFilterBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_content_types: set[ContentType] = {"post"}

            def filter_content(self, content: str) -> str:
                return content + "[filtered]"

        app = _app_with_plugin(base_config_data, "postonly", PostOnlyFilter)
        assert app.apply_content_filters("text", "post") == "text[filtered]"
        assert app.apply_content_filters("text", "page") == "text"
        assert app.apply_content_filters("text", "comment") == "text"

    def test_engine_allowlist_blocks_content_type_plugin_wants(self, app: Engine) -> None:
        """Engine allowlist overrides plugin's declared accepted_content_types."""

        class AllTypesFilter(ContentFilterBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_content_types: set[ContentType] = set(ALL_CONTENT_TYPES)

            def filter_content(self, content: str) -> str:
                return content + "[filtered]"

        f = AllTypesFilter({})
        app.plugins[ContentFilterBase].append(f)
        app.set_content_filter_allowlist(f, frozenset({"post"}))

        assert app.apply_content_filters("x", "post") == "x[filtered]"
        assert app.apply_content_filters("x", "page") == "x"
        assert app.apply_content_filters("x", "comment") == "x"

    def test_engine_allowlist_none_means_unrestricted(self, app: Engine) -> None:
        """None allowlist allows all content types the plugin declares."""

        class AllTypesFilter(ContentFilterBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_content_types: set[ContentType] = set(ALL_CONTENT_TYPES)

            def filter_content(self, content: str) -> str:
                return content + "[filtered]"

        f = AllTypesFilter({})
        app.plugins[ContentFilterBase].append(f)
        app.set_content_filter_allowlist(f, None)

        assert app.apply_content_filters("x", "post") == "x[filtered]"
        assert app.apply_content_filters("x", "comment") == "x[filtered]"

    def test_jinja_extensions_registered(self, base_config_data: dict[str, Any]) -> None:
        """get_jinja_extensions() classes must appear in engine.jinja_env.extensions."""
        app = _app_with_plugin(base_config_data, "jinjaext", JinjaExtPlugin)
        assert any("_DummyJinjaExtension" in k for k in app.jinja_env.extensions)
