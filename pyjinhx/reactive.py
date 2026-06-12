"""What a reactive component is and how it renders."""

from __future__ import annotations

import hashlib
import inspect
import json
from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Annotated, Any, ClassVar, get_args, get_origin

from markupsafe import Markup
from pydantic import ConfigDict, ModelWrapValidatorHandler, PrivateAttr, model_validator
from pydantic.fields import FieldInfo

from pyjinhx.base import BaseComponent
from pyjinhx.registry import Registry
from pyjinhx.renderer import Renderer
from pyjinhx.utils import (
    css_attribute_selector_attr_value,
    pascal_case_to_kebab_case,
    stamp_root_attributes,
)

from .cache import LoadCache
from .client import ClientBackend, MountedManifest
from .dev import warn_reactive_render_without_client
from .keys import MutationKey, ReactiveKey, coerce_load_key_str, coerce_reactive_keys
from .mutations import MutationTracker


class PjxKey:
    """Marker for ``Annotated[..., PjxKey()]`` fields stamped as ``data-pjx-load``."""


def _metadata_has_pjx_load(metadata: tuple[Any, ...]) -> bool:
    return any(isinstance(meta, PjxKey) for meta in metadata)


def _annotation_has_pjx_load(annotation: Any) -> bool:
    if get_origin(annotation) is Annotated:
        return _metadata_has_pjx_load(get_args(annotation)[1:])
    return False


def _field_has_pjx_load(field_info: FieldInfo) -> bool:
    if _metadata_has_pjx_load(field_info.metadata):
        return True
    return _annotation_has_pjx_load(field_info.annotation)


def pjx_load_field_names(model_cls: type[Any]) -> list[str]:
    names: list[str] = []
    for name, field_info in model_cls.model_fields.items():
        if _field_has_pjx_load(field_info):
            names.append(name)
    if names:
        return names
    # During __init_subclass__ pydantic has not yet populated model_fields, so
    # fall back to the raw annotations to detect the PjxKey marker at definition.
    for name, annotation in getattr(model_cls, "__annotations__", {}).items():
        if _annotation_has_pjx_load(annotation):
            names.append(name)
    return names


def resolve_pjx_load_field(model_cls: type[Any]) -> str | None:
    names = pjx_load_field_names(model_cls)
    if not names:
        return None
    if len(names) > 1:
        raise TypeError(
            f"{model_cls.__name__} declares multiple PjxKey fields {names!r}; "
            f"at most one is allowed."
        )
    return names[0]


def validate_pjx_load_subclass(
    cls: type[Any],
    *,
    keyed: bool,
) -> None:
    names = pjx_load_field_names(cls)
    if keyed and len(names) != 1:
        raise TypeError(
            f"{cls.__name__}.load() takes a resource argument; declare exactly "
            f"one field as Annotated[..., PjxKey()]."
        )
    if not keyed and names:
        raise TypeError(
            f"{cls.__name__}.load() takes no resource argument; PjxKey fields "
            f"are not allowed ({names!r})."
        )


def pjx_load_value(instance: Any) -> str | None:
    field_name = getattr(type(instance), "_pjx_load_field", None)
    if field_name is None:
        return None
    return coerce_load_key_str(getattr(instance, field_name, None))


class _ReactiveRender:
    """
    Expose ``render`` in two forms under one name on reactive components.

    - ``Cls.render(*args, **kwargs)`` — route entry: ``load(*args, **kwargs)`` then
      reactive bundle when a ``ClientBackend`` is active.
    - ``instance.render()`` — plain ``_render()`` only.
    """

    @staticmethod
    def _render_class(cls: type[ReactiveComponent], *args: Any, **kwargs: Any) -> Markup:
        keyed = getattr(cls, "_pjx_keyed", False)
        if keyed and not args:
            raise TypeError(
                f"{cls.__name__} is instance-keyed; render() requires the load() "
                f"resource argument, e.g. {cls.__name__}.render(<id>)."
            )
        if not keyed and args:
            raise TypeError(
                f"{cls.__name__} is a type-singleton; render() takes no arguments."
            )

        if not _reactive_context_active():
            instance = cls.load(*args, **kwargs) if keyed else cls.load(**kwargs)
            return Markup(instance._render(emit_assets=False))

        loaded: list[ReactiveComponent] = []

        def build_primary_tracked() -> str:
            instance = cls.load(*args, **kwargs) if keyed else cls.load(**kwargs)
            loaded.append(instance)
            return instance._render(emit_assets=False)

        return reactive_render_bundle(
            primary_html=build_primary_tracked,
            exclude_ids=lambda: {loaded[0].id} if loaded else set(),
            invalidate_before_primary=True,
        )

    def __get__(
        self,
        instance: ReactiveComponent | None,
        owner: type[ReactiveComponent],
    ) -> Callable[..., Markup]:
        if instance is None:
            return partial(_ReactiveRender._render_class, owner)

        def render() -> Markup:
            if not _reactive_context_active():
                return instance._render()
            return reactive_render_bundle(
                primary_html=lambda: instance._render(emit_assets=False),
                exclude_ids={instance.id},
                invalidate_before_primary=False,
            )

        return render


class ReactiveComponent(BaseComponent):
    """
    Base class for dependency-aware reactive components.

    A reactive component declares the state keys it derives from via the
    ``react`` class keyword — ``class Counter(ReactiveComponent, react={Keys.TODOS})``
    — and how to rebuild itself from the current world (``load()``). Both are
    required — ``load()`` is enforced by ABC (you cannot instantiate a subclass
    that does not implement it) and ``react`` is enforced at class-definition
    time; keys must be ``MutationKey`` members. A subclass without its own
    ``react`` inherits its parent's keys; declaring ``react`` replaces them
    (no union). Reactive components are stamped with ``data-pjx-*`` on render
    and are the units the dependency walk (``oob_swaps``) reloads and swaps.

    The ``id`` defaults to the kebab-cased class name (``TodoCounter`` ->
    ``"todo-counter"``), since a type-singleton's identity is its type — so ``load()``
    need not invent one. Pass an explicit ``id`` for instance-keyed regions (multiple
    mounted instances of one type, e.g. ``f"todo-row-{user_id}"``).
    """

    model_config = ConfigDict(extra="allow", ignored_types=(_ReactiveRender,))

    _pjx_framework: ClassVar[bool] = True

    state_hash_exclude: ClassVar[frozenset[str]] = frozenset({"id"})

    _pjx_key: str | None = PrivateAttr(default=None)
    _pjx_id_defaulted: bool = PrivateAttr(default=False)

    render = _ReactiveRender()

    @model_validator(mode="wrap")
    @classmethod
    def _default_id_from_type(
        cls, data: Any, handler: ModelWrapValidatorHandler[ReactiveComponent]
    ) -> ReactiveComponent:
        defaulted = isinstance(data, dict) and not data.get("id")
        if defaulted:
            data = {**data, "id": pascal_case_to_kebab_case(cls.__name__)}
        instance = handler(data)
        instance._pjx_id_defaulted = defaulted
        return instance

    @classmethod
    @abstractmethod
    def load(cls) -> ReactiveComponent:
        """Rebuild this component from the current world (zero-arg, type-singleton in v1)."""
        ...

    @staticmethod
    def _load_param_count(func: Any, owner: type[Any] | None = None) -> int:
        """Count ``load()`` parameters excluding ``cls``, PjxContext params, and variadics."""
        from .context import _is_load_context_param, _resolved_hints

        signature = inspect.signature(func)
        hints = _resolved_hints(func, owner)
        return sum(
            1
            for param in signature.parameters.values()
            if param.name != "cls"
            and not _is_load_context_param(param, hints)
            and param.kind
            not in (
                inspect.Parameter.VAR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            )
        )

    def depends_on(self) -> set[str]:
        """Reactive state keys this loaded instance currently depends on."""
        return set(getattr(type(self), "_pjx_reacts_to", frozenset()))

    def state_hash(self) -> str:
        """
        Stable content hash of this component's state, used to gate OOB swaps so a
        region whose value did not change is not re-sent. Defaults to a SHA-256 hex
        digest of canonical JSON from ``model_dump(mode="json")`` with
        ``state_hash_exclude`` applied (``id`` is excluded by default). Override for
        custom hashing.
        """
        exclude = getattr(type(self), "state_hash_exclude", frozenset({"id"}))
        payload = self.model_dump(mode="json", exclude=exclude)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def __init_subclass__(cls, react: set[MutationKey] | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "reacts_to" in cls.__dict__:
            raise TypeError(
                f"{cls.__name__}: reacts_to was replaced by the react class keyword: "
                f"class {cls.__name__}(ReactiveComponent, react={{...}})"
            )
        cls._pjx_reactive = True
        if react is not None:
            if isinstance(react, str):
                raise TypeError(
                    f"{cls.__name__}: react must be a set of MutationKey members, "
                    f"not a single key: react={{{react!r}}}"
                )
            invalid = sorted(repr(key) for key in react if not isinstance(key, MutationKey))
            if invalid:
                raise TypeError(
                    f"{cls.__name__}: react only accepts MutationKey members; "
                    f"got {', '.join(invalid)}"
                )
            cls._pjx_reacts_to = frozenset(coerce_reactive_keys(react))
        if "load" in cls.__dict__ and not getattr(cls, "_pjx_reacts_to", frozenset()):
            raise TypeError(
                f"{cls.__name__} defines load() but declares no react keys; declare "
                f"both: class {cls.__name__}(ReactiveComponent, react={{...}})"
            )
        if "load" in cls.__dict__:
            from .context import resolve_load_context_param

            _load = cls.__dict__["load"]
            _func = _load.__func__ if isinstance(_load, classmethod) else _load
            resolve_load_context_param(_func, cls)
            param_count = ReactiveComponent._load_param_count(_func, cls)
            if param_count > 1:
                raise TypeError(
                    f"{cls.__name__}.load() has {param_count} key parameters; "
                    f"at most one instance key is supported."
                )
            cls._pjx_keyed = param_count == 1
            validate_pjx_load_subclass(cls, keyed=cls._pjx_keyed)
            cls._pjx_load_field = resolve_pjx_load_field(cls)
        if "load" in cls.__dict__:
            LoadCache.install_cached_load(cls)


def _reactive_context_active() -> bool:
    backend = ClientBackend.current()
    if backend is None:
        return False
    if MutationTracker.pending():
        return True
    return bool(MountedManifest.parse(backend))


def reactive_render_bundle(
    *,
    primary_html: Markup | Callable[[], Markup | str],
    exclude_ids: set[str] | Callable[[], set[str]],
    invalidate_before_primary: bool,
) -> Markup:
    """
    Shared reactive render orchestration for class and instance ``render()`` paths.
    """
    backend = ClientBackend.current()
    warn_reactive_render_without_client(backend=backend)

    effective_dirtied = MutationTracker.pending()
    if invalidate_before_primary:
        LoadCache.invalidate(effective_dirtied)

    primary = primary_html() if callable(primary_html) else primary_html
    MutationTracker.mark_render_consumed()

    # Exclude only the primary (htmx swaps it as the main response). The trigger is
    # NOT excluded: a clicked region that depends on the dirtied keys must update
    # out-of-band like any other dependent (e.g. a "Clear (N)" button updating itself).
    resolved_exclude = set(exclude_ids() if callable(exclude_ids) else exclude_ids)

    swaps = oob_swaps(
        effective_dirtied,
        backend,
        exclude_ids=resolved_exclude,
        skip_invalidate=invalidate_before_primary,
    )
    return Markup(primary) + swaps


@dataclass
class _Candidate:
    """A dependency-matched region that has been reloaded and rendered."""

    id: str
    html: str
    fresh_hash: str | None
    reported_hash: str | None
    delete: bool = False


def _drop_nested(candidates: list[_Candidate]) -> list[_Candidate]:
    """
    Drop any candidate whose data-pjx-id marker appears inside another candidate's
    HTML — the parent's fresh HTML already contains the child, so a separate swap
    would be redundant (and would fight the parent's swap).
    """
    markers = {
        candidate.id: f'data-pjx-id="{candidate.id}"' for candidate in candidates
    }
    html_by_id = {candidate.id: candidate.html for candidate in candidates}
    surviving: list[_Candidate] = []
    for candidate in candidates:
        marker = markers[candidate.id]
        nested_in_other = any(
            marker in html_by_id[other.id]
            for other in candidates
            if other.id != candidate.id
        )
        if not nested_in_other:
            surviving.append(candidate)
    return surviving


def _oob_swap_selector(component_id: str) -> str:
    escaped_id = css_attribute_selector_attr_value(component_id)
    return f"outerHTML:[data-pjx-id='{escaped_id}']"


def _oob_delete_selector(component_id: str) -> str:
    escaped_id = css_attribute_selector_attr_value(component_id)
    return f"delete:[data-pjx-id='{escaped_id}']"


def _manifest_load_arg(entry: dict[str, Any]) -> str | None:
    load = entry.get("load")
    if load is None:
        return None
    return str(load)


def oob_swaps(
    dirtied: set[ReactiveKey],
    mounted: str | list[dict[str, Any]] | object | None,
    *,
    exclude_ids: set[str] | None = None,
    skip_invalidate: bool = False,
) -> Markup:
    """
    Compute out-of-band swap fragments for every mounted reactive region whose
    declared dependencies intersect the dirtied state keys.
    """
    dirtied_keys = coerce_reactive_keys(dirtied)
    if not skip_invalidate:
        LoadCache.invalidate(dirtied_keys)

    manifest = MountedManifest.parse(mounted)
    if not manifest:
        return Markup("")

    classes = Registry.get_classes()
    renderer = Renderer.get_default_renderer()

    candidates: list[_Candidate] = []
    seen: set[tuple[str, str | None]] = set()
    for entry in manifest:
        component_type = entry.get("type")
        component_id = entry.get("id")
        load_arg = _manifest_load_arg(entry)
        if not component_type or not component_id:
            continue
        if exclude_ids and component_id in exclude_ids:
            continue

        component_class = classes.get(component_type)
        if component_class is None:
            continue
        if not getattr(component_class, "_pjx_reactive", False):
            continue

        keyed = getattr(component_class, "_pjx_keyed", False)
        if keyed and load_arg is None:
            continue
        if not keyed:
            load_arg = None

        static_keys = set(getattr(component_class, "_pjx_reacts_to", frozenset()))
        if not (static_keys & dirtied_keys):
            continue

        dedup_key = (component_type, load_arg)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        reported_hash = entry.get("hash")
        try:
            if keyed and load_arg is not None:
                instance = component_class.load(load_arg)
            else:
                instance = component_class.load()
        except LookupError:
            candidates.append(
                _Candidate(
                    id=component_id,
                    html="",
                    fresh_hash=None,
                    reported_hash=reported_hash,
                    delete=True,
                )
            )
            continue

        instance.id = component_id
        fresh_hash = instance.state_hash()
        if fresh_hash == reported_hash:
            continue
        html = str(instance._render(_renderer=renderer, emit_assets=False))
        candidates.append(
            _Candidate(
                id=component_id,
                html=html,
                fresh_hash=fresh_hash,
                reported_hash=reported_hash,
            )
        )

    surviving = _drop_nested(candidates)
    if not surviving:
        return Markup("")

    fragments: list[str] = []
    for candidate in surviving:
        if candidate.delete:
            fragments.append(
                f'<div hx-swap-oob="{_oob_delete_selector(candidate.id)}"></div>'
            )
        else:
            fragments.append(
                stamp_root_attributes(
                    candidate.html, {"hx-swap-oob": _oob_swap_selector(candidate.id)}
                )
            )
    return Markup("\n".join(fragments))
