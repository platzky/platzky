"""Tests for typed capability plugin base classes and engine routing."""

from __future__ import annotations

from typing import Any, ClassVar
from unittest import mock

import jinja2.ext
import pytest

from platzky.attachment import Attachment
from platzky.config import Config
from platzky.content_types import ALL_CONTENT_TYPES, ContentType
from platzky.db.db import DB
from platzky.engine import Engine
from platzky.notification_topics import NotificationTopic
from platzky.page_sections import PageSection
from platzky.platzky import create_app_from_config, create_engine
from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.plugin.notifier import Notification, NotifierPluginBase
from platzky.plugin.page_decorator import PageDecoratorPluginBase
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

    def notify(self, notification: Notification) -> None:
        self.received.append((notification.message, notification.topic))


class SimpleAttachmentNotifier(NotifierPluginBase):
    """Notifier that records received messages and attachments."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_topics = frozenset(config.get("accepted_topics", _ALL_TOPICS))
        self.received: list[tuple[str, str, frozenset[Attachment]]] = []

    def notify(self, notification: Notification) -> None:
        self.received.append((notification.message, notification.topic, notification.attachments))


class TopicFilteredNotifier(NotifierPluginBase):
    """Notifier whose accepted_topics are configured via the config dict."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.accepted_topics = frozenset(config.get("accepted_topics", frozenset()))
        self.received: list[tuple[str, str]] = []

    def notify(self, notification: Notification) -> None:
        self.received.append((notification.message, notification.topic))


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

        app.notify("msg", topic="general", attachments=frozenset({fake_attachment}))  # type: ignore[arg-type]

        assert notifier.received[0][2] == frozenset({fake_attachment})

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
# Plugin base registration
# ---------------------------------------------------------------------------


class TestRegisterPluginBases:
    def test_uncategorised_plugin_raises_type_error(self, base_config_data: dict[str, Any]) -> None:
        class GenericPlugin(PluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)

        app = create_app_from_config(Config.model_validate(base_config_data))
        with pytest.raises(TypeError, match="does not implement any recognised capability"):
            app.register_plugin(GenericPlugin({}), "generic")

    def test_multi_capability_plugin_registered_under_all_bases(
        self, base_config_data: dict[str, Any]
    ) -> None:
        class MultiPlugin(NotifierPluginBase, ContentTransformerPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_topics: frozenset[NotificationTopic] = frozenset({"general"})
                self.accepted_content_types: frozenset[ContentType] = ALL_CONTENT_TYPES

            def notify(self, notification: Notification) -> None:
                pass  # no-op: test stub

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


# ---------------------------------------------------------------------------
# ContentType "field" — field-rendering opt-in
# ---------------------------------------------------------------------------


class TestFieldContentType:
    def test_field_in_all_content_types(self) -> None:
        assert "field" in ALL_CONTENT_TYPES

    def test_plugin_with_field_processes_field_content(
        self, base_config_data: dict[str, Any]
    ) -> None:
        class FieldReadyFilter(ContentTransformerPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_content_types: frozenset[ContentType] = frozenset({"field"})

            def transform_text(self, text: str) -> str:
                return text + "[field]"

        app = _app_with_plugin(base_config_data, "fieldready", FieldReadyFilter)
        assert app.transform_content("x", "field") == "x[field]"

    def test_plugin_without_field_skips_field_content(
        self, base_config_data: dict[str, Any]
    ) -> None:
        class PostOnlyFilter(ContentTransformerPluginBase):
            def __init__(self, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.accepted_content_types: frozenset[ContentType] = frozenset({"post"})

            def transform_text(self, text: str) -> str:
                return text + "[post]"

        app = _app_with_plugin(base_config_data, "postonlyfilter", PostOnlyFilter)
        assert app.transform_content("x", "field") == "x"


# ---------------------------------------------------------------------------
# PageDecoratorPluginBase
# ---------------------------------------------------------------------------


class HeadDecorator(PageDecoratorPluginBase):
    """Injects a fixed snippet into <head>."""

    accepted_page_sections: frozenset[PageSection] = frozenset({"head"})

    def get_head_html(self) -> str:
        """Return head HTML snippet."""
        return "<meta name='test'/>"


class BodyDecorator(PageDecoratorPluginBase):
    """Injects a fixed snippet at the start of <body>."""

    accepted_page_sections: frozenset[PageSection] = frozenset({"body"})

    def get_body_html(self) -> str:
        """Return body HTML snippet."""
        return "<div id='banner'></div>"


class HeadAndBodyDecorator(PageDecoratorPluginBase):
    """Injects into both <head> and <body>."""

    accepted_page_sections: frozenset[PageSection] = frozenset({"head", "body"})

    def get_head_html(self) -> str:
        """Return head HTML snippet."""
        return "<script>/*head*/</script>"

    def get_body_html(self) -> str:
        """Return body HTML snippet."""
        return "<script>/*body*/</script>"


class UndeclaredDecorator(PageDecoratorPluginBase):
    """Page decorator that forgets to declare accepted_page_sections."""

    def get_head_html(self) -> str:
        """Return head HTML snippet."""
        return "<meta name='undeclared'/>"


class TestPageDecoratorPluginBase:
    def test_head_injected_when_both_sides_declare_head(self, app: Engine) -> None:
        plugin = HeadDecorator({})
        app.plugins[PageDecoratorPluginBase].append(plugin)
        app.apply_page_decorator(plugin, frozenset({"head"}))

        assert "<meta name='test'/>" in app.dynamic_head

    def test_body_injected_when_both_sides_declare_body(self, app: Engine) -> None:
        plugin = BodyDecorator({})
        app.plugins[PageDecoratorPluginBase].append(plugin)
        app.apply_page_decorator(plugin, frozenset({"body"}))

        assert "<div id='banner'></div>" in app.dynamic_body

    def test_admin_cannot_inject_into_section_plugin_did_not_declare(self, app: Engine) -> None:
        plugin = HeadDecorator({})
        app.plugins[PageDecoratorPluginBase].append(plugin)
        app.apply_page_decorator(plugin, frozenset({"head", "body"}))

        assert "<meta name='test'/>" in app.dynamic_head
        assert app.dynamic_body == ""

    def test_plugin_cannot_inject_into_section_admin_did_not_allow(self, app: Engine) -> None:
        plugin = HeadAndBodyDecorator({})
        app.plugins[PageDecoratorPluginBase].append(plugin)
        app.apply_page_decorator(plugin, frozenset({"head"}))

        assert "<script>/*head*/</script>" in app.dynamic_head
        assert app.dynamic_body == ""

    def test_nothing_injected_when_allowlists_do_not_intersect(self, app: Engine) -> None:
        plugin = HeadDecorator({})
        app.plugins[PageDecoratorPluginBase].append(plugin)
        app.apply_page_decorator(plugin, frozenset({"body"}))

        assert app.dynamic_head == ""
        assert app.dynamic_body == ""

    def test_nothing_injected_when_admin_allowlist_empty(self, app: Engine) -> None:
        plugin = HeadAndBodyDecorator({})
        app.plugins[PageDecoratorPluginBase].append(plugin)
        app.apply_page_decorator(plugin, frozenset())

        assert app.dynamic_head == ""
        assert app.dynamic_body == ""

    def test_multiple_decorators_accumulate(self, app: Engine) -> None:
        head = HeadDecorator({})
        body = BodyDecorator({})
        for plugin in (head, body):
            app.plugins[PageDecoratorPluginBase].append(plugin)
            app.apply_page_decorator(plugin, frozenset({"head", "body"}))

        assert "<meta name='test'/>" in app.dynamic_head
        assert "<div id='banner'></div>" in app.dynamic_body

    def test_debug_logged_for_page_decorator_with_no_accepted_sections(
        self, app: Engine, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        with caplog.at_level(logging.DEBUG, logger="platzky.plugin"):
            app.load_plugin(
                UndeclaredDecorator, {}, "undeclared", allowed_page_sections=frozenset({"head"})
            )

        assert any("accepted_page_sections" in r.message for r in caplog.records)
        assert app.dynamic_head == ""

    def test_debug_logged_for_notifier_with_no_accepted_topics(
        self, app: Engine, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        class EmptyNotifier(NotifierPluginBase):
            """Notifier that forgets to declare accepted_topics."""

            def notify(self, notification: Notification) -> None:
                pass

        with caplog.at_level(logging.DEBUG, logger="platzky.plugin"):
            app.load_plugin(EmptyNotifier, {}, "empty_notifier")

        assert any("accepted_topics" in r.message for r in caplog.records)

    def test_debug_logged_for_transformer_with_no_accepted_content_types(
        self, app: Engine, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        class EmptyTransformer(ContentTransformerPluginBase):
            """Transformer that forgets to declare accepted_content_types."""

        with caplog.at_level(logging.DEBUG, logger="platzky.plugin"):
            app.load_plugin(EmptyTransformer, {}, "empty_transformer")

        assert any("accepted_content_types" in r.message for r in caplog.records)
