"""ContentTransformerPluginBase capability — plugins that transform content."""

from __future__ import annotations

import logging
from abc import ABC
from collections.abc import Iterable, Mapping
from typing import ClassVar, cast

import jinja2.ext
from markupsafe import escape

from platzky.content_types import ALL_CONTENT_TYPES, ContentType
from platzky.plugin.plugin import PluginBase
from platzky.plugin.plugin_config import PluginConfigBase
from platzky.shortcodes import Shortcode
from platzky.shortcodes.parser import render_document


class ContentTransformerPluginConfig(PluginConfigBase):
    """Plugin config for ContentTransformerPluginBase — carries the content-type allowlist."""

    allowed_content_types: frozenset[ContentType] = frozenset()


logger = logging.getLogger(__name__)


class ContentTransformerPluginBase(PluginBase, ABC):
    """Base class for content-transformer plugins.

    Subclasses declare which content types they want to transform via
    ``accepted_content_types``. That declaration is the set of choices a site owner is
    offered, not a grant: they still name each type in ``allowed_content_types``, and
    silence is refusal.

    A plugin with no technical constraint on where it runs declares
    ``ALL_CONTENT_TYPES`` — offering every type in the vocabulary, including ones invented
    after it was written. A plugin that does have a constraint names each type it can
    serve: one whose shortcode emits block-level layout markup, reaches an external host,
    or costs something to run cannot honestly claim to work anywhere, and naming its types
    is how it says so.

    Naming types is *not* how a plugin keeps itself out of comments — whether commenters
    may use it is the site owner's policy, and their grant already decides it. A plugin may
    also name a kind of content some other package brings — accepting one never means
    importing that package — and still install on an
    application that has no such content, where it is simply never called. To *bring* a
    content type, see ``PluginBase.provides_content_types``. The engine enforces final
    routing — ``Engine.may_transform`` decides, not the plugin, so widening
    ``accepted_content_types`` cannot widen the site owner's grant.

    Declare ``shortcodes`` to register shortcode tags; they are applied automatically by
    ``Engine.transform_content``, which is the only thing that runs a plugin — a plugin
    never transforms content itself, because running one is the registry's job and the
    gate is where it makes its decision. An application rendering a *stored value*
    through ``Shortcode.render_value`` bypasses ``transform_content`` entirely, so it
    must take its shortcodes from ``Engine.shortcodes_for`` to stay behind the same
    gate rather than reading ``shortcodes`` off loaded plugins itself.

    Override ``transform_text`` to
    apply plain-text transformations — the framework guarantees that
    ``transform_text`` is never called with shortcode tag markup so
    transformations cannot accidentally mangle tags intended for other plugins.
    """

    accepted_content_types: Mapping[ContentType, str] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Reject a declaration that asks for a content type without saying why.

        Required, not encouraged: the rationale is shown beside the checkbox a site owner
        ticks, and a reason nothing enforces is a reason that rots.

        Raises:
            ValueError: If a declared content type carries no rationale.
        """
        super().__init_subclass__(**kwargs)
        declared = cls.__dict__.get("accepted_content_types")
        if declared is None:
            return
        if not isinstance(declared, Mapping):
            raise ValueError(
                f"{cls.__name__}.accepted_content_types must map each content type to the "
                f"reason this plugin needs it; got {type(declared).__name__}."
            )
        # The annotation promises str values, but nothing enforces annotations at runtime
        # and a plugin is a third-party package that may never have been type-checked. The
        # cast says so, so the checks below are not read as redundant.
        for content_type, reason in cast("Mapping[object, object]", declared).items():
            if not isinstance(reason, str) or not reason.strip():
                name = "ALL_CONTENT_TYPES" if content_type is ALL_CONTENT_TYPES else content_type
                raise ValueError(
                    f"{cls.__name__}.accepted_content_types[{name!r}] needs a reason a "
                    f"site owner can read when deciding whether to grant it."
                )

    shortcodes: ClassVar[dict[str, Shortcode]] = {}

    def transform_text(self, text: str) -> str:
        """Apply plain-text transformation to a non-tag content segment.

        Override this to transform plain text while the framework ensures
        shortcode tags are never passed here.

        Args:
            text: Plain-text segment (no shortcode tag markup).

        Returns:
            Transformed text.
        """
        return text

    def get_jinja_extensions(self) -> list[type[jinja2.ext.Extension]]:
        """Return Jinja2 extension classes to register with the template engine.

        Returns:
            Jinja2 extension classes to register; empty list by default.
        """
        return []


class ContentTransformerRegistry:
    """The gate deciding which content transformers may act on which content.

    Holds the content-type vocabulary transformers route on and each plugin's
    allowlist the site owner granted, and applies both when dispatching. Kept apart from the
    engine so the routing rules sit beside the capability base they govern and the
    config model that defines the grant, and so they can be exercised without an app.

    What it does not own is which transformers exist and in what order: ``Engine.plugins``
    is that, uniformly for every capability, and the list arrives as a dispatch argument.
    Three things keep it there. Transformers chain, so their order is semantic, and it is
    set in two places — ``register_plugin`` appends, while ``platzky.py`` inserts the
    builtin shortcodes at index 0 to run ahead of any plugin filter. One instance may
    implement several capabilities and is registered under each, so only the engine sees
    the whole picture. And applications add capability bases of their own through
    ``extra_plugin_bases``, which ``register_plugin`` covers generically; a capability
    owning its plugins would be a second registration path that mechanism misses.

    It does hold a reference to every granted plugin, since the allowlist is keyed by
    instance — membership and order are what live elsewhere, not the plugins themselves.
    """

    def __init__(self, known_content_types: Iterable[ContentType] = ()) -> None:
        """Initialise the gate.

        Args:
            known_content_types: The vocabulary in place before any plugin loads —
                platzky's builtins plus whatever the application registers.
        """
        self.known_content_types: set[ContentType] = set(known_content_types)
        self._allowlist: dict[ContentTransformerPluginBase, frozenset[ContentType]] = {}
        self._grants_reported = False

    def grant(
        self, plugin: ContentTransformerPluginBase, allowed_types: frozenset[ContentType]
    ) -> None:
        """Record the site owner's grant for a plugin.

        One call because it is one decision: the same allowlist entry is what
        ``may_transform`` enforces and what ``warn_unknown_grants`` later checks. An empty
        frozenset blocks every content type, as does never granting a plugin at all.
        Called by the plugin loader; not intended to be called from plugin code.

        Args:
            plugin: The plugin the grant applies to. Its class names it in any later
                warning.
            allowed_types: Content types the site owner granted it.
        """
        self._allowlist[plugin] = allowed_types

    def may_transform(
        self, plugin: ContentTransformerPluginBase, content_type: ContentType
    ) -> bool:
        """Return whether this plugin may act on this kind of content.

        Offer and grant must agree: the plugin's own ``accepted_content_types`` declaration
        and the site owner's grant. The allowlist lives here and a plugin never receives it,
        so widening ``accepted_content_types`` at runtime changes the offer and not the
        grant. Default-deny: an unlisted plugin is blocked, as is an empty grant.

        ``ALL_CONTENT_TYPES`` offers anything in the vocabulary, and nothing more — the
        site owner still names each type they want acted on.

        Args:
            plugin: The content-transformer plugin to check.
            content_type: The kind of content it wants to act on.

        Returns:
            True if the plugin is both willing and permitted.
        """
        if content_type not in self.acceptable_content_types(plugin):
            return False
        return content_type in self._allowlist.get(plugin, frozenset())

    def offered_content_types(self, plugin: ContentTransformerPluginBase) -> dict[ContentType, str]:
        """This plugin's declaration resolved: every type it is offered, and why.

        The one place the wildcard is expanded. A declaration that names types is already
        this mapping; one keyed with ``ALL_CONTENT_TYPES`` becomes every type in the
        vocabulary against that single reason. Everything downstream reads the result and
        never the sentinel, so there is no second shape of the same question.

        The sentinel is found by identity rather than looked up, because
        ``ALL_CONTENT_TYPES`` is a ``str`` subclass: ``declared.get(ALL_CONTENT_TYPES)``
        would also find a content type literally named ``"*"`` and read it as the wildcard.

        Resolved on each call rather than cached, because plugins contribute content types
        as they load and the vocabulary is only complete once loading is done.

        Args:
            plugin: The plugin whose declaration to resolve.

        Returns:
            Each content type this plugin may be granted, mapped to its rationale.
        """
        declared = plugin.accepted_content_types
        for content_type, reason in declared.items():
            if content_type is ALL_CONTENT_TYPES:
                return dict.fromkeys(self.known_content_types, reason)
        return dict(declared)

    def acceptable_content_types(self, plugin: ContentTransformerPluginBase) -> set[ContentType]:
        """The content types a site owner may grant this plugin.

        The set of choices, not the decision: an admin panel offers exactly these and the
        site owner ticks the ones they want, which become ``allowed_content_types``.

        Args:
            plugin: The plugin whose declaration to resolve.

        Returns:
            The content types this plugin may be granted.
        """
        return set(self.offered_content_types(plugin))

    def rationale_for(self, plugin: ContentTransformerPluginBase, content_type: ContentType) -> str:
        """Why this plugin is asking for this content type, in its author's words.

        Shown beside the checkbox a site owner ticks. A plugin that names its types gives a
        reason per type; one declaring ``ALL_CONTENT_TYPES`` gives a single reason that
        stands for every type it is offered.

        Args:
            plugin: The plugin whose declaration to read.
            content_type: The content type being offered.

        Returns:
            The rationale, or an empty string if this plugin is not offered that type.
        """
        return self.offered_content_types(plugin).get(content_type, "")

    def transform_content(
        self,
        plugins: Iterable[ContentTransformerPluginBase],
        content: str,
        content_type: ContentType,
        *,
        strip_html: bool = False,
    ) -> str:
        """Run every permitted transformer over the content, in order.

        Transformers chain their output, so a failing transformer aborts the chain rather
        than silently passing partial output to the next stage.

        Content is escaped on the way in unless the caller vouched for it by passing
        ``Markup`` — the caller is the only party that knows where it came from, so the
        default is the safe one and vouching is the deliberate act. Everything the
        pipeline adds afterwards is markup platzky itself produced, by plugins that turned
        offered and granted this content type, so it is trusted by construction and shortcodes
        embed their content directly. See ``Shortcode.render``.

        Args:
            plugins: Content transformers in registration order.
            content: The content to transform. A plain ``str`` is treated as untrusted and
                escaped; a ``Markup`` is taken as vouched for and passed through.
            content_type: The kind of content, e.g. ``POST``.
            strip_html: Overrule vouching and remove HTML tags the author wrote, keeping
                the text they wrapped and logging what went. The site owner's call, behind
                ``STRIP_CONTENT_HTML``: shortcodes still render, but a site turning it on
                needs some other way to format a post, because HTML is currently the only
                one platzky has. A ``"raw"`` shortcode body is exempt: it is verbatim by
                declaration, which makes it the way an author marks HTML they mean to
                keep. Only vouched content has one — unvouched content is escaped at the
                boundary, raw bodies included.

        Returns:
            The content after every permitted transformer has run.
        """
        # Whether anyone vouched decides three separate things, so read it before escaping
        # flattens the Markup away: what gets escaped, whose mistakes get reported, and
        # whether there is any authored HTML left for the site owner to strip.
        vouched = hasattr(content, "__html__")
        # escape() is a no-op on anything carrying __html__, so this is the whole rule.
        # It makes content safe; it does not stop shortcode parsing. Brackets survive, so
        # a bare tag in untrusted content still fires — harmlessly, since what it wraps is
        # already escaped — while a quoted attribute does not survive and that tag renders
        # literally. Safety does not depend on which happens.
        content = str(escape(content))
        # That mangling is also why only vouched content is parsed strictly. Escaping the
        # quotes out of `[tag a="b"]x[/tag]` leaves an opening tag that no longer matches
        # and a closing tag that does, so a stranger writing an ordinary shortcode would
        # otherwise fail the render — a typo in a comment must not take a page down.
        permitted = [p for p in plugins if self.may_transform(p, content_type)]
        # One parse for the whole pipeline, then any stripping, then every filter, then
        # every shortcode. The plugins are no longer run one after another over a flat
        # string: doing that made each stage re-derive the document the previous one had
        # just discarded, and handed every filter the markup earlier shortcodes had
        # produced.
        rendered, removed = render_document(
            content,
            self.shortcodes_for(permitted, content_type),
            [plugin.transform_text for plugin in permitted],
            strict=vouched,
            # Unvouched content was escaped above, raw bodies with it, so it has no tags
            # left to strip and no way to pass one through a raw body either.
            strip_html=strip_html and vouched,
        )
        if removed:
            # Lossy and silent otherwise, so say what went and how much of it.
            logger.warning(
                "Removed %d HTML tag(s) from %s content (%s) because STRIP_CONTENT_HTML "
                "is on. The text they wrapped was kept.",
                len(removed),
                content_type,
                ", ".join(sorted(set(removed))),
            )
        return rendered

    def shortcodes_for(
        self, plugins: Iterable[ContentTransformerPluginBase], content_type: ContentType
    ) -> dict[str, Shortcode]:
        """Return the shortcodes permitted to render this kind of content.

        The gate an application needs when it renders a *stored value* through
        ``Shortcode.render_value`` instead of transforming prose. That call does not pass
        through ``transform_content``, so an application collecting shortcodes off its
        loaded plugins itself would honour neither the plugin's declaration nor the
        site owner's grant — the grant would silently govern nothing.

        Args:
            plugins: Content transformers in registration order.
            content_type: The kind of content the shortcodes will render.

        Returns:
            Permitted shortcodes keyed by tag name. A name registered by more than one
            permitted plugin is taken from the *first*, which is the same one prose gets:
            transformers run in order and the first to own a tag consumes it, so a later
            registration could never have rendered it anyway. Taking the last here would
            make a stored value render differently from the identical tag in a post body.
        """
        permitted: dict[str, Shortcode] = {}
        owners: dict[str, str] = {}
        for plugin in plugins:
            if not self.may_transform(plugin, content_type):
                continue
            for tag_name, shortcode in plugin.shortcodes.items():
                if tag_name in permitted:
                    logger.warning(
                        "Plugin %r registers shortcode %r, already registered by %r for "
                        "content type '%s'. The earlier plugin wins; reorder the plugins "
                        "in the config to change which.",
                        type(plugin).__name__,
                        tag_name,
                        owners[tag_name],
                        content_type,
                    )
                    continue
                permitted[tag_name] = shortcode
                owners[tag_name] = type(plugin).__name__
        return permitted

    def warn_unknown_grants(self) -> None:
        """Warn about granted content types no plugin or application ever registered.

        The vocabulary is open, so an unknown type cannot be rejected: an application
        registers its own, and a plugin may name one this application does not have — a
        plugin built for another application installs cleanly and stays inert, which is
        deliberate. A grant naming a type nothing produces is almost always a typo in
        site-owner config, though, and silently grants nothing, so say so rather than
        leaving a transformer mysteriously idle.

        Called by the plugin loader once every plugin is loaded, so that a plugin
        contributing a content type need not load before the plugins granted it. Reading
        the allowlist rather than a log of grants is what makes that safe: the vocabulary
        is complete by now, and a plugin granted twice is judged on the grant it ended up
        with. Reports once — a second call is a no-op, since the answer cannot have
        changed without another plugin loading.
        """
        if self._grants_reported:
            return
        self._grants_reported = True
        for plugin, allowed in self._allowlist.items():
            for unknown in sorted(allowed - self.known_content_types):
                logger.warning(
                    "Plugin %s is granted content type '%s', which this application does not "
                    "produce; the grant has no effect. Known types: %s",
                    type(plugin).__name__,
                    unknown,
                    ", ".join(sorted(self.known_content_types)),
                )
