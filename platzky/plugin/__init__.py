"""Plugin base classes for the Platzky plugin system."""

from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.plugin.login import LoginPluginBase
from platzky.plugin.notifier import NotifierPluginBase
from platzky.plugin.page_decorator import PageDecoratorPluginBase
from platzky.plugin.plugin import PluginBase

# Kept as an explicit tuple rather than auto-discovered via __init_subclass__ so
# that only platzky maintainers can define what counts as a capability. A registry
# pattern would let third-party plugins inject new bases, bypassing the engine's
# dispatch contract.
PLUGIN_BASES: tuple[type[PluginBase], ...] = (
    NotifierPluginBase,
    ContentTransformerPluginBase,
    LoginPluginBase,
    PageDecoratorPluginBase,
)
