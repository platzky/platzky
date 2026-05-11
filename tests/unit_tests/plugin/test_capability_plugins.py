"""Tests for typed capability plugin base classes and engine routing."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar
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
from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.plugin.notifier import AttachmentNotifierPluginBase, NotifierPluginBase
from platzky.plugin.plugin import PluginBase
from platzky.shortcodes import Shortcode, ShortcodeAttrs

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
    base_config_data["DB"]["DATA"]["plugins"] = [
        {
            "name": name,
            "config": {},
            "allowed_content_types": list(ALL_CONTENT_TYPES),
            "allowed_topics": ["general", "content", "security"],
        }
    ]
    config = Config.model_validate(base_config_data)
    ep = mock.MagicMock()
    ep.name = name
    ep.load.return_value = plugin_class
    with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
        return create_app_from_config(config)


# ---------------------------------------------------------------------------
# NotifierPluginBase
# ---------------------------------------------------------------------------

_ALL_TOPICS: set[NotificationTopic] = {"general", "content", "security"}


class SimpleNotifier(NotifierPluginBase):
    """Notifier that accepts all topics and records received messages."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_topics = frozenset(config.get("accepted_topics", _ALL_TOPICS))
        self.received: list[tuple[str, str]] = []

    def notify(
        self,
        message: str,
        topic: NotificationTopic,
        receiver: str = "",  # noqa: ARG002
    ) -> None:
        self.received.append((message, topic))


class SimpleAttachmentNotifier(AttachmentNotifierPluginBase):
    """Attachment-aware notifier that records received messages and attachments."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_topics = frozenset(config.get("accepted_topics", _ALL_TOPICS))
        self.received: list[tuple[str, str, Sequence[AttachmentProtocol]]] = []

    def notify_with_attachments(
        self,
        message: str,
        topic: NotificationTopic,
        attachments: Sequence[AttachmentProtocol],
        receiver: str = "",  # noqa: ARG002
    ) -> None:
        self.received.append((message, topic, attachments))


class TopicFilteredNotifier(NotifierPluginBase):
    """Notifier whose accepted_topics are configured via the config dict."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_topics = frozenset(config.get("accepted_topics", frozenset()))
        self.received: list[tuple[str, str]] = []

    def notify(
        self,
        message: str,
        topic: NotificationTopic,
        receiver: str = "",  # noqa: ARG002
    ) -> None:
        self.received.append((message, topic))


class TestNotifierPluginBase:
    def test_notifier_receives_matching_topic(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        app.plugins[NotifierPluginBase].append(notifier)
        app.set_notifier_allowlist(notifier, frozenset(_ALL_TOPICS))

        app.notify("hello", topic="general")

        assert notifier.received == [("hello", "general")]

    def test_notifier_only_receives_declared_topics(self, app: Engine) -> None:
        notifier = TopicFilteredNotifier({"accepted_topics": ["security"]})
        app.plugins[NotifierPluginBase].append(notifier)
        app.set_notifier_allowlist(notifier, frozenset(_ALL_TOPICS))

        app.notify("breach", topic="security")
        app.notify("new post", topic="content")
        app.notify("hi", topic="general")

        assert len(notifier.received) == 1
        assert notifier.received[0][1] == "security"

    def test_engine_allowlist_blocks_topic_plugin_wants(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        app.plugins[NotifierPluginBase].append(notifier)
        app.set_notifier_allowlist(notifier, frozenset({"general"}))

        app.notify("breach", topic="security")
        app.notify("hi", topic="general")

        assert len(notifier.received) == 1
        assert notifier.received[0][1] == "general"

    def test_engine_without_allowlist_is_blocked(self, app: Engine) -> None:
        notifier = SimpleNotifier({})
        app.plugins[NotifierPluginBase].append(notifier)

        app.notify("breach", topic="security")
        app.notify("hi", topic="general")

        assert len(notifier.received) == 0

    def test_new_topic_not_received_without_explicit_opt_in(self, app: Engine) -> None:
        security_only = TopicFilteredNotifier({"accepted_topics": ["security"]})
        app.plugins[NotifierPluginBase].append(security_only)
        app.set_notifier_allowlist(security_only, frozenset(_ALL_TOPICS))

        app.notify("new topic message", topic="general")

        assert len(security_only.received) == 0

    def test_notify_routes_by_topic(self, app: Engine) -> None:
        security_only = TopicFilteredNotifier({"accepted_topics": ["security"]})
        all_topics = SimpleNotifier({})
        app.plugins[NotifierPluginBase].extend([security_only, all_topics])
        app.set_notifier_allowlist(security_only, frozenset(_ALL_TOPICS))
        app.set_notifier_allowlist(all_topics, frozenset(_ALL_TOPICS))

        app.notify("breach detected", topic="security")
        app.notify("new post", topic="content")

        assert len(security_only.received) == 1
        assert security_only.received[0][1] == "security"
        assert len(all_topics.received) == 2

    def test_notify_with_attachments_forwarded(self, app: Engine) -> None:
        notifier = SimpleAttachmentNotifier({})
        app.plugins[NotifierPluginBase].append(notifier)
        app.set_notifier_allowlist(notifier, frozenset(_ALL_TOPICS))
        fake_attachment = object()

        app.notify("msg", topic="general", attachments=[fake_attachment])  # type: ignore[list-item]

        assert notifier.received[0][2] == [fake_attachment]

    def test_accepted_topics_from_config_list(self) -> None:
        notifier = TopicFilteredNotifier({"accepted_topics": ["security", "content"]})
        assert isinstance(notifier.accepted_topics, frozenset)
        assert notifier.accepted_topics == frozenset({"security", "content"})


# ---------------------------------------------------------------------------
# ContentTransformerPluginBase
# ---------------------------------------------------------------------------


class _ShoutShortcode(Shortcode):
    name = "shout"
    description = "Upper-case content."

    def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
        """Return content in upper case."""
        return content.upper()


class ShoutFilter(ContentTransformerPluginBase):
    """Registers a [shout] shortcode that upper-cases its content."""

    accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES
    shortcodes: ClassVar[dict[str, Shortcode]] = {"shout": _ShoutShortcode()}


class TestContentTransformerPluginBase:
    def test_default_returns_empty_dict(self) -> None:
        class NoOpFilter(ContentTransformerPluginBase):
            accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES

        f = NoOpFilter({})
        assert f.shortcodes == {}

    def test_override_registers_shortcode(self) -> None:
        f = ShoutFilter({})
        assert "shout" in f.shortcodes
        assert f.shortcodes["shout"].render(ShortcodeAttrs([]), "hello") == "HELLO"

    def test_filters_registered_under_capability_key(
        self, base_config_data: dict[str, Any]
    ) -> None:
        app = _app_with_plugin(base_config_data, "shout", ShoutFilter)
        assert any(
            isinstance(p, ShoutFilter) for p in app.get_plugins(ContentTransformerPluginBase)
        )

    def test_shortcodes_from_multiple_plugins_chainable(self) -> None:
        class _ATagSC(Shortcode):
            name = "atag"
            description = "wrap in A"

            def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
                """Wrap content in A()."""
                return f"A({content})"

        class _BTagSC(Shortcode):
            name = "btag"
            description = "wrap in B"

            def render(self, attrs: ShortcodeAttrs, content: str) -> str:  # noqa: ARG002
                """Wrap content in B()."""
                return f"B({content})"

        class AFilter(ContentTransformerPluginBase):
            accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES
            shortcodes: ClassVar[dict[str, Shortcode]] = {"atag": _ATagSC()}

        class BFilter(ContentTransformerPluginBase):
            accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES
            shortcodes: ClassVar[dict[str, Shortcode]] = {"btag": _BTagSC()}

        combined = {**AFilter.shortcodes, **BFilter.shortcodes}

        class _CombinedTestPlugin(ContentTransformerPluginBase):
            accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES

        _CombinedTestPlugin.shortcodes = combined
        result = _CombinedTestPlugin({}).transform_content("[atag]x[/atag] [btag]y[/btag]")
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
        assert not any(isinstance(p, GenericPlugin) for p in app.get_plugins(NotifierPluginBase))

    def test_plugin_stored_under_concrete_type(self, base_config_data: dict[str, Any]) -> None:
        app = _app_with_plugin(base_config_data, "simple", SimpleNotifier)
        assert any(isinstance(p, SimpleNotifier) for p in app.get_plugins(SimpleNotifier))

    def test_multi_capability_plugin_registered_under_all_bases(
        self, base_config_data: dict[str, Any]
    ) -> None:
        class MultiPlugin(NotifierPluginBase, ContentTransformerPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_topics: frozenset[NotificationTopic] = frozenset({"general"})
                self.accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES

            def notify(
                self,
                message: str,
                topic: NotificationTopic,
                receiver: str = "",
            ) -> None:
                # No-op: only verifies capability registration, not notification delivery.
                pass

        app = _app_with_plugin(base_config_data, "multi", MultiPlugin)
        assert any(isinstance(p, MultiPlugin) for p in app.get_plugins(NotifierPluginBase))
        assert any(
            isinstance(p, MultiPlugin) for p in app.get_plugins(ContentTransformerPluginBase)
        )


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
        assert infos[0].description == (SimpleNotifier.__doc__ or "").strip()


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
        class NewPlugin(NotifierPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_topics: frozenset[NotificationTopic] = frozenset({"general"})

            def notify(
                self,
                message: str,
                topic: NotificationTopic,
                receiver: str = "",
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
# ContentTransformerPluginBase wiring in create_app_from_config
# ---------------------------------------------------------------------------


class ShoutTagPlugin(ContentTransformerPluginBase):
    """Registers a [shout] shortcode."""

    accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES
    shortcodes: ClassVar[dict[str, Shortcode]] = {"shout": _ShoutShortcode()}


class _DummyJinjaExtension(jinja2.ext.Extension):
    tags = {"dummy_tag"}  # noqa: RUF012


class JinjaExtPlugin(ContentTransformerPluginBase):
    """Test filter that exposes a Jinja2 extension."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES

    def get_jinja_extensions(self) -> list[type[jinja2.ext.Extension]]:
        return [_DummyJinjaExtension]


class AllTypesFilter(ContentTransformerPluginBase):
    """Content transformer that accepts all content types."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES

    def transform_text(self, text: str) -> str:
        return text + "[filtered]"


class TestContentTransformerWiring:
    def test_shortcode_registered_in_engine(self, base_config_data: dict[str, Any]) -> None:
        """Plugin shortcodes must appear in engine.shortcodes after app creation."""
        app = _app_with_plugin(base_config_data, "shout", ShoutTagPlugin)
        assert "shout" in app.shortcodes

    def test_transform_content_applies_shortcode(self, base_config_data: dict[str, Any]) -> None:
        """transform_content() must transform content via the plugin's shortcode handler."""
        app = _app_with_plugin(base_config_data, "shout", ShoutTagPlugin)
        assert any(
            isinstance(p, ShoutTagPlugin) for p in app.get_plugins(ContentTransformerPluginBase)
        )
        result = app.transform_content("[shout]hello[/shout]", "post")
        assert result == "HELLO"

    def test_filter_only_applied_to_declared_content_type(
        self, base_config_data: dict[str, Any]
    ) -> None:
        """Plugins only receive content types listed in accepted_content_types."""

        class PostOnlyFilter(ContentTransformerPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_content_types: frozenset[ContentType] = frozenset({"post"})

            def transform_text(self, text: str) -> str:
                return text + "[filtered]"

        app = _app_with_plugin(base_config_data, "postonly", PostOnlyFilter)
        assert app.transform_content("text", "post") == "text[filtered]"
        assert app.transform_content("text", "page") == "text"
        assert app.transform_content("text", "comment") == "text"

    def test_engine_allowlist_blocks_content_type_plugin_wants(self, app: Engine) -> None:
        """Engine allowlist overrides plugin's declared accepted_content_types."""
        f = AllTypesFilter({})
        app.plugins[ContentTransformerPluginBase].append(f)
        app.set_content_transformer_allowlist(f, frozenset({"post"}))

        assert app.transform_content("x", "post") == "x[filtered]"
        assert app.transform_content("x", "page") == "x"
        assert app.transform_content("x", "comment") == "x"

    def test_engine_without_allowlist_is_blocked(self, app: Engine) -> None:
        """Plugin with no allowlist registered is blocked for all content types."""
        f = AllTypesFilter({})
        app.plugins[ContentTransformerPluginBase].append(f)

        assert app.transform_content("x", "post") == "x"
        assert app.transform_content("x", "comment") == "x"

    def test_builtin_shortcodes_applied_by_engine(self, base_config_data: dict[str, Any]) -> None:
        """Builtin [image] shortcode must be resolved by the engine pipeline."""
        config = Config.model_validate(base_config_data)
        app = create_app_from_config(config)
        result = app.transform_content('[image url="https://example.com/x.png" alt="x"]', "post")
        assert '<img src="https://example.com/x.png"' in result

    def test_transform_text_does_not_mangle_html_from_earlier_transformer(
        self, base_config_data: dict[str, Any]
    ) -> None:
        """transform_text must not receive HTML tags produced by earlier transformers."""

        class AToXFilter(ContentTransformerPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES

            def transform_text(self, text: str) -> str:
                return text.replace("a", "X")

        app = _app_with_plugin(base_config_data, "atox", AToXFilter)
        result = app.transform_content('<img alt="anchor">', "post")
        assert result == '<img alt="anchor">'

    def test_jinja_extensions_registered(self, base_config_data: dict[str, Any]) -> None:
        """get_jinja_extensions() classes must appear in engine.jinja_env.extensions."""
        app = _app_with_plugin(base_config_data, "jinjaext", JinjaExtPlugin)
        assert any("_DummyJinjaExtension" in k for k in app.jinja_env.extensions)
