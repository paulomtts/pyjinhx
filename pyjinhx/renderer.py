from __future__ import annotations

import logging
import os
import re
import threading
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, ClassVar

from jinja2 import Environment, FileSystemLoader, Template
from jinja2.exceptions import TemplateNotFound
from jinja2.runtime import Context
from jinja2.utils import missing
from markupsafe import Markup

from .assets import (
    AssetMode,
    AssetPolicy,
    RenderSession,
    apply_component_render_assets,
    inject_assets,
)
from .finder import Finder
from .registry import Registry
from .root_attrs import apply_root_attrs
from .tags import Parser, contains_custom_tag, expand_custom_tags, render_tag_node
from .utils import (
    component_resolution_classes,
    detect_root_directory,
    tag_name_to_template_filenames,
)

if TYPE_CHECKING:
    from .base import BaseComponent

logger = logging.getLogger("pyjinhx")

# Unlocked by choice: a lost race here means at most a duplicate warning /
# repeated probe, never wrong output (issue #240 audit).
# Dedup set: component names for which the stale-def-header warning has fired.
_warned_stale_def_header: set[str] = set()

# Component names whose template has already been checked for a stale header,
# whether or not it had one. Keeps the file read + regex check to at most once
# per class per process instead of on every render.
_checked_stale_def_header: set[str] = set()

# Cheap regex — mirrors _HEADER_RE in props_header.py, without the full parse.
_STALE_DEF_HEADER_RE = re.compile(r"\A\s*\{#\s*def\s", re.DOTALL)


def get_loader_root(environment: Environment) -> str:
    loader = environment.loader
    if not isinstance(loader, FileSystemLoader):
        raise ValueError("Jinja2 loader must be a FileSystemLoader")  # noqa: TRY004 (public API, documented ValueError)
    return Finder.get_loader_root(loader)


def get_finder_for_root(renderer: Renderer, search_root: str) -> Finder:
    finder = renderer._template_finder_cache.get(search_root)
    if finder is None:
        with renderer._cache_lock:
            finder = renderer._template_finder_cache.get(search_root)
            if finder is None:
                finder = Finder(search_root)
                renderer._template_finder_cache[search_root] = finder
    return finder


def load_template_for_component(
    renderer: Renderer,
    component: BaseComponent,
    *,
    template_source: str | None,
    template_path: str | None,
) -> Template:
    environment = renderer.environment
    if template_source is not None:
        return environment.from_string(template_source)

    if template_path is not None:
        loader_root = get_loader_root(environment)
        relative_path = os.path.relpath(template_path, loader_root)
        return environment.get_template(relative_path)

    # Html-only components synthesized via `component(name)` have no real source
    # file, so resolve their template by scanning the default env by tag name.
    pjx_template = getattr(type(component), "_pjx_template", None)
    if pjx_template is not None:
        try:
            found_path = renderer._find_template_for_tag(pjx_template)
        except FileNotFoundError:
            from .tags import _missing_template_error

            raise _missing_template_error(pjx_template)
        loader_root = get_loader_root(environment)
        relative_path = os.path.relpath(found_path, loader_root)
        return environment.get_template(relative_path)

    component_type = type(component)
    cached_relative_path = renderer._template_path_cache.get(component_type)
    if cached_relative_path is not None:
        return environment.get_template(cached_relative_path)

    resolution_classes = component_resolution_classes(component_type)
    if not resolution_classes:
        raise FileNotFoundError(
            "No template found. Use a BaseComponent subclass with an adjacent template file, "
            "or use Renderer.render() with PascalCase tags."
        )

    loader_root = get_loader_root(environment)
    attempted: list[str] = []
    for klass in resolution_classes:
        relative_template_paths = Finder.get_relative_template_paths(
            component_dir=Finder.get_class_directory(klass),
            search_root=loader_root,
            component_name=klass.__name__,
        )
        attempted.extend(relative_template_paths)
        for relative_template_path in relative_template_paths:
            try:
                template = environment.get_template(relative_template_path)
            except TemplateNotFound:
                continue
            with renderer._cache_lock:
                renderer._template_path_cache[component_type] = relative_template_path
            return template
        if klass.__module__.startswith("pyjinhx.builtins"):
            component_dir = Finder.get_class_directory(klass)
            for filename in tag_name_to_template_filenames(klass.__name__):
                candidate_path = os.path.join(component_dir, filename)
                cached_template = renderer._builtin_template_cache.get(candidate_path)
                if cached_template is not None:
                    return cached_template
                if os.path.isfile(candidate_path):
                    with renderer._cache_lock:
                        cached_template = renderer._builtin_template_cache.get(candidate_path)
                        if cached_template is None:
                            with open(candidate_path, encoding="utf-8") as template_file:
                                cached_template = environment.from_string(template_file.read())
                            renderer._builtin_template_cache[candidate_path] = cached_template
                    return cached_template

    raise TemplateNotFound(", ".join(attempted) if attempted else "unknown")


_render_state: ContextVar[tuple[Renderer, RenderSession, dict[str, Any]] | None] = (
    ContextVar("pyjinhx_render_state", default=None)
)
"""The renderer, session and render context of the component currently being
rendered by ``Renderer.render_component_with_context``.

A ContextVar rather than an attribute on the Jinja ``Context``: Jinja builds
fresh ``Context`` objects for ``{% include %}``, ``{% import %}``, macros and
loop-scoped blocks through paths we don't control, and they'd all lose an
attribute we'd set by hand. They do all run inside the same call stack, so the
ContextVar reaches them uniformly. Set/reset around the render call, so nested
component renders push and pop their own state.
"""


class _PjxContext(Context):
    """Jinja context that resolves an unknown name against the registry peers.

    Registry instances used to be merged into every component's render context
    by id (``{**session.registry_defaults, **context}``), then copied again by
    Jinja's ``new_context`` — O(registered instances) per node, O(N^2) per page
    (#240). Templates only ever *look up* peers by name, so the lookup happens
    here instead: one dict ``get``, no copying and no iteration. Nothing about
    the peers goes into the render-context dict, which matters because
    ``BaseComponent._build_template_context`` walks that dict and must never
    see the live, still-growing ``registry_defaults``.

    Precedence matches the old ``{**defaults, **context}`` merge: an explicit
    context value wins over a peer, and a peer wins over an environment global
    of the same name. Hits are wrapped in ``LazyNestedComponentWrapper``
    exactly as the old undeclared-fields loop in ``_build_template_context``
    did, so ``{{ peer }}``, ``{{ peer.html }}`` and ``{{ peer.props.field }}``
    behave identically and peers still render only when referenced (#67).

    The ContextVar-backed peer resolution is scoped to the call stack rather
    than to any one ``Context`` instance, so peers now also resolve inside
    ``{% import %}`` and ``{% include ... without context %}`` — templates
    the old per-render dict merge never reached.
    """

    def resolve_or_missing(self, key: str) -> Any:
        value = super().resolve_or_missing(key)
        state = _render_state.get()
        if state is None:
            return value

        renderer, session, own_context = state
        if value is not missing:
            # A hit that could only have come from the environment globals
            # still falls through to the registry: peers used to be merged
            # into the context `vars`, which Jinja layers on top of the
            # globals, so a peer has always shadowed a global of the same
            # name. `self.environment.globals` (not `self.globals_keys`) is
            # used here because `Context.derived()` (used for e.g.
            # `{% block scoped %}`) builds derived contexts with
            # `globals=None`, leaving `globals_keys` empty there even though
            # the environment globals are still very much in effect.
            from_globals = (
                key in self.environment.globals
                and key not in self.vars
                and key not in own_context
            )
            if not from_globals:
                return value

        instance = session.registry_defaults.get(key)
        if instance is None:
            return value

        from .base import LazyNestedComponentWrapper

        peer = LazyNestedComponentWrapper(
            instance, own_context, renderer=renderer, session=session
        )
        # Remember it so `{{ peer }}` and `{{ peer.html }}` in one template
        # share a single deferred render, like the dict entry the old
        # python-level merge left behind.
        self.vars[key] = peer
        return peer


def build_render_context(
    context: dict[str, Any], session: RenderSession
) -> dict[str, Any]:
    """Fold registry instances registered since the last node into the
    session's peer cache and return the node's own render context.

    The peers themselves are deliberately NOT merged into the returned dict —
    ``_PjxContext`` resolves them lazily by name at the Jinja layer instead.
    """
    ordered_instances = Registry.get_instances_in_order()
    if len(ordered_instances) != session.registry_scanned:
        # `ordered_instances` only ever grows within a render pass, so the
        # entries already folded into `registry_defaults` are still valid —
        # just fold in the tail that's new since the last node rendered.
        for instance in ordered_instances[session.registry_scanned :]:
            session.registry_defaults.setdefault(instance.id, instance)
        session.registry_scanned = len(ordered_instances)

    return context


def reactive_root_attrs(
    component: BaseComponent, *, precomputed_hash: str | None = None
) -> dict[str, str]:
    """The ``data-pjx-*`` attributes to stamp onto a reactive component's root
    tag, or an empty dict for a non-reactive component.

    ``precomputed_hash``, when given, is stamped verbatim instead of calling
    ``component.state_hash()`` again. Callers that already computed the exact
    same instance's hash moments earlier (e.g. the OOB dirty-check in
    ``oob_swaps``) pass it through here to avoid paying for a second
    ``model_dump`` + ``sha256`` pass over the same, unchanged state.
    """
    from pyjinhx.reactive import ReactiveComponent

    if not isinstance(component, ReactiveComponent):
        return {}

    from pyjinhx.reactive import pjx_load_value

    attrs = {
        "data-pjx-id": component.id,
        "data-pjx-type": type(component).__name__,
        "data-pjx-hash": precomputed_hash if precomputed_hash is not None else component.state_hash(),
    }
    load_value = pjx_load_value(component)
    if load_value is not None:
        attrs["data-pjx-load"] = load_value
    reacts = getattr(type(component), "_pjx_reacts_to", frozenset())
    if reacts:
        attrs["data-pjx-reacts"] = " ".join(sorted(reacts))
    return attrs


def _warn_if_stale_def_header(component: BaseComponent, template: Template) -> None:
    """Emit a one-time warning when a hand-written class has a {#def#} header in its template.

    The header is silently ignored by the engine (the class's declared fields take over),
    so a warning helps developers notice the dead code.  Skips classless components
    (_pjx_classless = True) and fires at most once per component name.
    """
    if getattr(type(component), "_pjx_classless", False):
        return

    component_name = type(component).__name__
    if component_name in _checked_stale_def_header:
        return
    _checked_stale_def_header.add(component_name)

    # Read the template source cheaply: file-backed templates expose .filename;
    # in-memory (from_string) templates expose .source (Jinja2 >=3.1 sets it
    # only when Environment.keep_trailing_newline is used, so prefer .filename).
    source: str | None = None
    filename = getattr(template, "filename", None)
    if filename is not None and os.path.isfile(filename):
        try:
            with open(filename, encoding="utf-8") as f:
                source = f.read()
        except OSError:
            return
    else:
        source = getattr(template, "source", None)

    if source is None:
        return

    if not _STALE_DEF_HEADER_RE.match(source):
        return

    _warned_stale_def_header.add(component_name)
    logger.warning(
        "<%s>: a {#def#} header is present but a Python class is registered — "
        "the header is ignored. Remove the header (or the class).",
        component_name,
    )


# Private-use-area marker: vanishingly unlikely to appear in real HTML/text,
# never matches the PascalCase tag regex (no literal "<"), safe inside both a
# text node and an attribute value. Written as an explicit escape (not a
# literal glyph) so it can't be silently stripped by an editor/copy-paste
# pipeline. If adversarial or round-tripped content already contains this
# marker, `_opacify_rendered_markup` detects that and bails out (opacifying
# nothing) rather than risk restoring a slot value into the wrong place.
_SLOT_PLACEHOLDER_CHAR = "\ue000"


def _collect_opacifiable_slot_values(context: dict[str, Any]) -> list[str]:
    """Collect already-fully-expanded ``Markup`` slot values that are safe to
    opacify in the *rendered output* (see ``_opacify_rendered_markup``).

    Mirrors the shape ``base._wrap_slot_value`` produces (a scalar ``Markup``,
    or a ``list``/``dict`` of ``Markup``). A value qualifies only when it
    contains zero PascalCase-tag-looking substrings — a value containing
    literal tag text (e.g. ``Card(content="<Icon/>")``) must still go through
    the full ``expand_custom_tags`` scan, so it's never a candidate here. An
    empty ``Markup("")`` is also excluded — it can never appear as a
    meaningful substring match anyway, and excluding it keeps this function's
    contract simple (no candidate is ever falsy).

    Takes the component's OWN ``context`` (its field values). Registry peers
    never appear here — they are resolved lazily by name at the Jinja layer
    (``_PjxContext``) and are always ``BaseComponent`` objects, never
    ``Markup``, so they could never be a candidate anyway.

    This runs against the values a template *could* embed — not against the
    rendered output itself; matching against the actual output is
    ``_opacify_rendered_markup``'s job, and its two-step split (collect
    candidates from context, then search-and-replace against the real
    rendered string) is what lets a template inspect (``|length``, ``in``,
    ``|striptags``, slicing, ...) a slot value with its real content during
    ``template.render()`` — the substitution never touches the context, only
    the string handed to ``expand_custom_tags`` afterward, and only where the
    value was actually emitted unchanged.

    This closes the gap for a component's own direct emit-and-inspect of its
    own slot value. It does NOT close it for a value passed further into a
    nested custom tag's own template: if this component emits the value
    inside another PascalCase tag (e.g. ``<Wrapper>{{ content }}</Wrapper>``),
    the child (``Wrapper``) receives the placeholder token — not the real
    HTML — as its own slot field's rendered text, so an inspection inside
    *its* template still sees the token. That narrower case is unaffected by
    this function; see ``render_component_with_context``, where the
    substitution and its restoration both happen at the level of the
    component whose context originally held the value.
    """
    candidates: list[str] = []
    visited_containers: set[int] = set()

    def visit(value: Any) -> None:
        if isinstance(value, Markup):
            if value and not contains_custom_tag(value):
                candidates.append(str(value))
        elif isinstance(value, (list, dict)):
            if id(value) in visited_containers:
                return
            visited_containers.add(id(value))
            if isinstance(value, list):
                for item in value:
                    visit(item)
            else:
                for item in value.values():
                    visit(item)

    for value in context.values():
        visit(value)
    return candidates


def _opacify_rendered_markup(
    markup: str, candidates: list[str]
) -> tuple[str, dict[str, str]]:
    """Replace verbatim occurrences of already-safe candidate values in
    ``markup`` with short opaque placeholder tokens, so the following
    ``expand_custom_tags`` call doesn't need to re-tokenize them with
    ``html.parser`` just because some other part of ``markup`` still has a
    new tag to expand.

    A candidate that isn't found verbatim in ``markup`` (because the
    template transformed it — ``|striptags``, concatenation, slicing, ...  —
    before embedding it) is simply skipped: nothing to opacify there, and
    ``expand_custom_tags`` scans that portion in full, exactly as it would
    without this optimization. This is what makes output-substitution safe
    for templates that inspect slot values, unlike substituting into the
    render context before ``template.render()`` runs.

    Longest candidates are tried first, so a short candidate that happens to
    be a substring of a longer one never partially corrupts the longer
    match. Tokens are call-local: generated and restored within one
    ``render_component_with_context`` invocation, so no cross-level
    bookkeeping or global uniqueness is needed.

    Adversarial or round-tripped content can already contain the marker
    character; opacifying on top of that would let the restore pass splice
    an unrelated slot's HTML into that location. So if the marker is already
    present anywhere in ``markup``, this bails out entirely -- returning the
    markup unchanged and no placeholders -- rather than risk that.
    """
    # Adversarial or round-tripped content can already contain the marker;
    # opacifying then would restore a slot value into the wrong place.
    if _SLOT_PLACEHOLDER_CHAR in markup:
        return markup, {}

    placeholders: dict[str, str] = {}
    for value in sorted(set(candidates), key=len, reverse=True):
        if value not in markup:
            continue
        token = f"{_SLOT_PLACEHOLDER_CHAR}{len(placeholders)}{_SLOT_PLACEHOLDER_CHAR}"
        placeholders[token] = value
        markup = markup.replace(value, token)
    return markup, placeholders


def _restore_opacified_slots(markup: str, placeholders: dict[str, str]) -> str:
    for token, original in placeholders.items():
        markup = markup.replace(token, original)
    return markup


class Renderer:
    """
    Shared rendering engine used by `BaseComponent` rendering and HTML-like custom-tag rendering.

    This renderer centralizes:
    - Process-wide defaults and cached default-renderer factory
    - Jinja template loading (by component class or explicit file/source)
    - Expansion of PascalCase custom tags inside rendered markup
    - JavaScript collection/deduping and root-level script injection
    - Rendering of HTML-like source strings into component output
    """

    _default_environment: ClassVar[Environment | None] = None
    _default_js_mode: ClassVar[AssetMode] = AssetMode.INLINE
    _default_css_mode: ClassVar[AssetMode] = AssetMode.INLINE
    _default_renderers: ClassVar[
        dict[tuple[int, bool, AssetMode, AssetMode], Renderer]
    ] = {}

    @classmethod
    def peek_default_environment(cls) -> Environment | None:
        return cls._default_environment

    @classmethod
    def set_default_environment(
        cls, environment: Environment | str | os.PathLike[str] | None
    ) -> None:
        if environment is None or isinstance(environment, Environment):
            cls._default_environment = environment
        else:
            cls._default_environment = Environment(
                loader=FileSystemLoader(os.fspath(environment)),
                autoescape=True,
            )
        cls._default_renderers.clear()

    @classmethod
    def set_default_js_mode(cls, mode: AssetMode) -> None:
        cls._default_js_mode = mode
        cls._default_renderers.clear()

    @classmethod
    def set_default_css_mode(cls, mode: AssetMode) -> None:
        cls._default_css_mode = mode
        cls._default_renderers.clear()

    @classmethod
    def get_default_environment(cls) -> Environment:
        if cls._default_environment is None:
            root_dir = detect_root_directory()
            cls._default_environment = Environment(
                loader=FileSystemLoader(root_dir), autoescape=True
            )
        return cls._default_environment

    @classmethod
    def get_default_renderer(
        cls,
        *,
        auto_id: bool = True,
        js_mode: AssetMode | None = None,
        css_mode: AssetMode | None = None,
    ) -> Renderer:
        environment = cls.get_default_environment()
        effective_js_mode = js_mode if js_mode is not None else cls._default_js_mode
        effective_css_mode = css_mode if css_mode is not None else cls._default_css_mode
        cache_key = (
            id(environment),
            auto_id,
            effective_js_mode,
            effective_css_mode,
        )
        renderer = cls._default_renderers.get(cache_key)
        if renderer is None:
            renderer = cls(
                environment,
                auto_id=auto_id,
                js_mode=effective_js_mode,
                css_mode=effective_css_mode,
            )
            cls._default_renderers[cache_key] = renderer
        return renderer

    def __init__(
        self,
        environment: Environment,
        *,
        auto_id: bool = True,
        js_mode: AssetMode | None = None,
        css_mode: AssetMode | None = None,
    ) -> None:
        self._environment = environment
        # Deliberate (idempotent) mutation of a possibly caller-supplied
        # environment: it only changes what happens when a name misses, and
        # only to look the name up among the render session's registry peers.
        environment.context_class = _PjxContext
        self._auto_id = auto_id
        self._js_mode = js_mode if js_mode is not None else Renderer._default_js_mode
        self._css_mode = css_mode if css_mode is not None else Renderer._default_css_mode
        self._template_finder_cache: dict[str, Finder] = {}
        self._builtin_template_cache: dict[str, Template] = {}
        self._template_path_cache: dict[type, str] = {}
        self._cache_lock = threading.Lock()

    @property
    def environment(self) -> Environment:
        return self._environment

    def new_session(self) -> RenderSession:
        return RenderSession()

    def _find_template_for_tag(self, tag_name: str) -> str:
        loader_root = get_loader_root(self._environment)
        finder = get_finder_for_root(self, loader_root)
        return finder.find_template_for_tag(tag_name)

    def render_component_with_context(
        self,
        component: BaseComponent,
        context: dict[str, Any],
        template_source: str | None,
        template_path: str | None,
        session: RenderSession,
        is_root: bool,
        collect_component_js: bool,
        *,
        emit_assets: bool = True,
        client: object | None = None,
        extra_root_attrs: dict[str, str] | None = None,
    ) -> Markup:
        template = load_template_for_component(
            self, component, template_source=template_source, template_path=template_path
        )

        _warn_if_stale_def_header(component, template)

        render_context = build_render_context(context, session)
        # Registry peers are resolved by name during the render, out of the
        # session rather than out of `render_context` (see `_PjxContext`).
        state_token = _render_state.set((self, session, render_context))
        try:
            rendered_markup = template.render(render_context)
        finally:
            _render_state.reset(state_token)
        candidates = _collect_opacifiable_slot_values(context)
        safe_markup, placeholders = _opacify_rendered_markup(rendered_markup, candidates)
        expanded_markup = str(
            expand_custom_tags(
                self,
                safe_markup,
                base_context=render_context,
                session=session,
                emit_assets=emit_assets,
            )
        )
        from .base import collect_extra_attrs

        extra_root_attrs = extra_root_attrs or {}
        # A caller that already computed this exact instance's state_hash()
        # moments earlier (the OOB dirty-check in oob_swaps) can pass it
        # through as "data-pjx-hash" here to skip a redundant model_dump +
        # sha256 pass over the same, unchanged state.
        attrs = {
            **collect_extra_attrs(component),
            **reactive_root_attrs(
                component, precomputed_hash=extra_root_attrs.get("data-pjx-hash")
            ),
            **extra_root_attrs,
        }
        component_name = type(component).__name__
        # Stamp root attrs while child slot values are still collapsed to
        # opaque tokens: the root scanner then parses this component's own
        # template output, not the accumulated markup of every descendant.
        # If the root scan fails on the token form (e.g. the template's whole
        # body is a slot, so no element is visible), restore and re-validate
        # against the real document so error behavior matches the un-opacified
        # path exactly.
        try:
            stamped_markup = apply_root_attrs(
                expanded_markup, component_name=component_name, attrs=attrs
            )
        except ValueError:
            if not placeholders:
                raise
            expanded_markup = _restore_opacified_slots(expanded_markup, placeholders)
            placeholders = {}
            stamped_markup = apply_root_attrs(
                expanded_markup, component_name=component_name, attrs=attrs
            )
        if placeholders:
            stamped_markup = _restore_opacified_slots(stamped_markup, placeholders)
        rendered_markup = Markup(stamped_markup)

        if not emit_assets:
            return Markup(rendered_markup)

        policy = AssetPolicy(
            js_mode=self._js_mode,
            css_mode=self._css_mode,
        )
        # For classless components built via the factory path, template_path is
        # None (the renderer resolved the template internally via _pjx_template).
        # Compute the effective asset path so apply_component_render_assets can
        # find co-located CSS/JS next to the template file.
        asset_template_path = template_path
        if asset_template_path is None and getattr(type(component), "_pjx_classless", False):
            pjx_template = getattr(type(component), "_pjx_template", None)
            if pjx_template is not None:
                try:
                    asset_template_path = self._find_template_for_tag(pjx_template)
                except FileNotFoundError:
                    asset_template_path = None
        rendered_markup = apply_component_render_assets(
            component,
            rendered_markup,
            session,
            template_path=asset_template_path,
            is_root=is_root,
            collect_component_js=collect_component_js,
            policy=policy,
            client=client,
        )
        return Markup(rendered_markup)

    def render(self, source: str) -> str:
        parser = Parser()
        parser.feed(source)
        parser.close()

        session = self.new_session()
        rendered_markup = "".join(
            render_tag_node(
                self,
                node,
                base_context={},
                session=session,
                emit_assets=True,
            )
            for node in parser.root_nodes
        )
        if self._css_mode != AssetMode.NONE or self._js_mode != AssetMode.NONE:
            policy = AssetPolicy(
                js_mode=self._js_mode,
                css_mode=self._css_mode,
            )
            rendered_markup = inject_assets(rendered_markup, session, policy=policy)
        return rendered_markup.strip()
