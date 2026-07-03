"""Plugin base classes for the Platzky plugin system."""

from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.plugin.html_injector import HtmlInjectorPluginBase
from platzky.plugin.login import LoginPluginBase
from platzky.plugin.notifier import NotifierPluginBase
from platzky.plugin.plugin import PluginBase

# Kept as an explicit tuple rather than auto-discovered via __init_subclass__ so that
# plugin *discovery* can never inject a capability base: an installed package must not
# gain a capability just by being present, since each capability carries an
# engine-enforced allowlist that auto-injection would bypass.
#
# The application that *composes* the engine via ``create_app_from_config`` owns its
# plugin ecosystem and may extend it explicitly with ``extra_plugin_bases`` (and
# ``extra_plugins_entrypoints`` for discovery) — this is host-owned, not granted to
# arbitrary installed packages.
PLUGIN_BASES: tuple[type[PluginBase], ...] = (
    NotifierPluginBase,
    ContentTransformerPluginBase,
    LoginPluginBase,
    HtmlInjectorPluginBase,
)
