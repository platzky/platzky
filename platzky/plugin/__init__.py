"""Plugin capability base classes for the Platzky plugin system."""

from platzky.plugin.content_transformer import ContentTransformerPluginBase
from platzky.plugin.login import LoginPluginBase
from platzky.plugin.notifier import AttachmentNotifierPluginBase, NotifierPluginBase
from platzky.plugin.plugin import PluginBase

CAPABILITY_BASES: tuple[type[PluginBase], ...] = (
    NotifierPluginBase,
    AttachmentNotifierPluginBase,
    ContentTransformerPluginBase,
    LoginPluginBase,
)
