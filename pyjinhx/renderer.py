from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING, Any, ClassVar

from jinja2 import Environment, FileSystemLoader, Template
from jinja2.exceptions import TemplateNotFound
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
from .tags import Parser, expand_custom_tags, render_tag_node
from .utils import (
    component_resolution_classes,
    detect_root_directory,
    tag_name_to_template_filenames,
)

if TYPE_CHECKING:
    from .base import BaseComponent

logger = logging.getLogger("pyjinhx")

# Dedup set: component names for which the stale-def-header warning has fired.
_warned_stale_def_header: set[str] = set()

# Cheap regex — mirrors _HEADER_RE in props_header.py, without the full parse.
_STALE_DEF_HEADER_RE = re.compile(r"\A\s*\{#\s*def\s", re.DOTALL)


def get_loader_root(environment: Environment) -> str:
    loader = environment.loader
    if not isinstance(loader, FileSystemLoader):
        raise ValueError("Jinja2 loader must be a FileSystemLoader")
    return Finder.get_loader_root(loader)


def get_finder_for_root(renderer: Renderer, search_root: str) -> Finder:
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

    resolution_classes = component_resolution_classes(type(component))
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
                return environment.get_template(relative_template_path)
            except TemplateNotFound:
                continue
        if klass.__module__.startswith("pyjinhx.builtins"):
            component_dir = Finder.get_class_directory(klass)
            for filename in tag_name_to_template_filenames(klass.__name__):
                candidate_path = os.path.join(component_dir, filename)
                if os.path.isfile(candidate_path):
                    with open(candidate_path, encoding="utf-8") as template_file:
                        return environment.from_string(template_file.read())

    raise TemplateNotFound(", ".join(attempted) if attempted else "unknown")


def build_render_context(context: dict[str, Any]) -> dict[str, Any]:
    render_context = dict(context)
    for instance in Registry.get_instances().values():
        render_context.setdefault(instance.id, instance)
    return render_context


def reactive_root_attrs(component: BaseComponent) -> dict[str, str]:
    """The ``data-pjx-*`` attributes to stamp onto a reactive component's root
    tag, or an empty dict for a non-reactive component."""
    from pyjinhx.reactive import ReactiveComponent

    if not isinstance(component, ReactiveComponent):
        return {}

    from pyjinhx.reactive import pjx_load_value

    attrs = {
        "data-pjx-id": component.id,
        "data-pjx-type": type(component).__name__,
        "data-pjx-hash": component.state_hash(),
    }
    load_value = pjx_load_value(component)
    if load_value is not None:
        attrs["data-pjx-load"] = load_value
    reacts = getattr(type(component), "_pjx_reacts_to", frozenset())
    if reacts:
        attrs["data-pjx-reacts"] = " ".join(sorted(reacts))
    return attrs


def _warn_if_stale_def_header(component: "BaseComponent", template: Template) -> None:
    """Emit a one-time warning when a hand-written class has a {#def#} header in its template.

    The header is silently ignored by the engine (the class's declared fields take over),
    so a warning helps developers notice the dead code.  Skips classless components
    (_pjx_classless = True) and fires at most once per component name.
    """
    if getattr(type(component), "_pjx_classless", False):
        return

    component_name = type(component).__name__
    if component_name in _warned_stale_def_header:
        return

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
        dict[tuple[int, bool, AssetMode, AssetMode], "Renderer"]
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
    ) -> "Renderer":
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
        self._auto_id = auto_id
        self._js_mode = js_mode if js_mode is not None else Renderer._default_js_mode
        self._css_mode = css_mode if css_mode is not None else Renderer._default_css_mode
        self._template_finder_cache: dict[str, Finder] = {}

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

        render_context = build_render_context(context)
        rendered_markup = template.render(render_context)
        rendered_markup = expand_custom_tags(
            self,
            rendered_markup,
            base_context=render_context,
            session=session,
            emit_assets=emit_assets,
        )
        from .base import collect_extra_attrs
        from .root_attrs import apply_root_attrs

        attrs = {
            **collect_extra_attrs(component),
            **reactive_root_attrs(component),
            **(extra_root_attrs or {}),
        }
        rendered_markup = Markup(
            apply_root_attrs(
                str(rendered_markup),
                component_name=type(component).__name__,
                attrs=attrs,
            )
        )

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
