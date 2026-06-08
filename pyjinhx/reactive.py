from __future__ import annotations

import hashlib
import inspect
import json
import logging
from abc import abstractmethod
from dataclasses import dataclass
from functools import partial
from collections.abc import Callable
from typing import Any, ClassVar

from markupsafe import Markup
from pydantic import ConfigDict, PrivateAttr, model_validator

from .base import BaseComponent
from .cache import invalidate
from .registry import Registry
from .assets import AssetMode, DEFAULT_RUNTIME_URL
from .renderer import Renderer
from .utils import (
    ReactiveKey,
    coerce_load_key_str,
    coerce_reactive_keys,
    interpolate_reactive_keys,
    pascal_case_to_kebab_case,
    read_client_runtime,
    stamp_root_attributes,
)

logger = logging.getLogger("pyjinhx")

PJX_MOUNTED_HEADER = "X-PJX-Mounted"
"""Name of the HTTP header carrying the client's mounted-region manifest."""

PJX_ASSETS_HEADER = "X-PJX-Assets"
"""Name of the HTTP header carrying asset URLs already loaded in the browser."""


def _load_param_count(func: Any) -> int:
    """Count ``load()`` parameters excluding ``cls``, ``ctx``, and variadics."""
    params = inspect.signature(func).parameters
    return sum(
        1
        for name, param in params.items()
        if name not in ("cls", "ctx")
        and param.kind
        not in (
            inspect.Parameter.VAR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        )
    )


def client_script(
    *,
    mode: AssetMode | None = None,
    src: str | None = None,
) -> Markup:
    """
    Return the pyjinhx client runtime as a ``<script>`` tag.

    Drop this into a page shell (e.g. a raw Jinja layout) to emit the
    ``X-PJX-Mounted`` manifest header on every htmx request. When the page shell
    is marked ``base_layout=True`` the runtime is injected automatically and you
    do not need to call this.

    Args:
        mode: ``AssetMode.INLINE`` (default) inlines the runtime source.
            ``AssetMode.REFERENCE`` emits ``<script src="...">``.
        src: Public URL for the runtime when ``mode`` is ``AssetMode.REFERENCE``.
            Defaults to ``Renderer``'s configured runtime URL.
    """
    effective_mode = mode or AssetMode.INLINE
    if effective_mode == AssetMode.REFERENCE:
        runtime_url = src or Renderer._default_runtime_url or DEFAULT_RUNTIME_URL
        return Markup(f'<script src="{runtime_url}"></script>')
    return Markup(f"<script>{read_client_runtime()}</script>")


class _ReactiveRender:
    """
    Expose ``render`` in two forms under one name on reactive components.

    - ``Cls.render(key=None, *, dirtied=None, mounted=None)`` — the route entry
      point: auto-``load()``s the primary (by key for keyed types) and appends OOB
      swaps for dependents. The developer never names ``load()`` or ``oob_swaps()``.
    - ``instance.render(*, dirtied=None, mounted=None)`` — render an already-built
      instance as the primary; same contract as ``BaseComponent.render``.

    A plain ``classmethod`` would shadow the instance method and make
    ``instance.render()`` re-load from the world, dropping the instance's own state;
    the descriptor dispatches on access so both forms coexist.
    """

    @staticmethod
    def _render_class(
        cls: type[ReactiveComponent],
        key: object | None = None,
        *,
        dirtied: set[ReactiveKey] | None = None,
        mounted: object | None = None,
    ) -> Markup:
        """
        Route entry point for a reactive primary: auto-``load()`` it, render it, and
        append OOB swaps for its dependents. The developer never calls ``load()`` —
        the key (identity) is forwarded to ``load()`` here. Non-identity context is
        sourced by ``load()`` itself (it is ambient: the dependency walk reloads
        dependents from the manifest knowing only their key, so nothing else can be
        forwarded).
        """
        keyed = getattr(cls, "_pjx_keyed", False)
        if keyed and key is None:
            raise TypeError(
                f"{cls.__name__} is instance-keyed; render() requires a key, e.g. "
                f"{cls.__name__}.render(<id>, dirtied=..., mounted=request)."
            )
        if not keyed and key is not None:
            raise TypeError(
                f"{cls.__name__} is a type-singleton; render() takes no key."
            )

        skey = coerce_load_key_str(key) if key is not None else None
        from .mutations import mark_reactive_render_consumed, resolve_effective_dirtied
        from .reactive_dev import warn_reactive_render_without_mounted

        own_keys = interpolate_reactive_keys(
            getattr(cls, "_pjx_reacts_to", frozenset()), skey, keyed=keyed
        )
        warn_reactive_render_without_mounted(
            dirtied=dirtied, mounted=mounted, own_keys=own_keys
        )
        effective_dirtied = resolve_effective_dirtied(
            dirtied=dirtied,
            mounted=mounted,
            own_keys=own_keys,
        )
        invalidate(effective_dirtied | own_keys)
        instance = cls.load(skey) if keyed else cls.load()
        primary = instance._render(emit_assets=False)
        mark_reactive_render_consumed()
        swaps = oob_swaps(effective_dirtied, mounted, exclude_ids={instance.id})
        return Markup(primary) + swaps

    def __get__(
        self,
        instance: ReactiveComponent | None,
        owner: type[ReactiveComponent],
    ) -> Callable[..., Markup]:
        if instance is None:
            return partial(_ReactiveRender._render_class, owner)
        return partial(BaseComponent.render, instance)


class ReactiveComponent(BaseComponent):
    """
    Base class for dependency-aware reactive components.

    A reactive component declares the state keys it derives from (``reacts_to``)
    and how to rebuild itself from the current world (``load()``). Both are
    required — ``load()`` is enforced by ABC (you cannot instantiate a subclass
    that does not implement it) and ``reacts_to`` is enforced at class-definition
    time. Reactive components are stamped with ``data-pjx-*`` on render and are the
    units the dependency walk (``oob_swaps``) reloads and swaps.

    The ``id`` defaults to the kebab-cased class name (``TodoCounter`` ->
    ``"todo-counter"``), since a type-singleton's identity is its type — so ``load()``
    need not invent one. Pass an explicit ``id`` for instance-keyed regions (multiple
    mounted instances of one type, e.g. ``f"todo-row-{user_id}"``).
    """

    model_config = ConfigDict(extra="allow", ignored_types=(_ReactiveRender,))

    reacts_to: ClassVar[set[ReactiveKey]] = set()
    load_reads: ClassVar[set[ReactiveKey]] = set()

    _pjx_key: str | None = PrivateAttr(default=None)

    render = _ReactiveRender()

    @model_validator(mode="before")
    @classmethod
    def _default_id_from_type(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("id"):
            return {**data, "id": pascal_case_to_kebab_case(cls.__name__)}
        return data

    @classmethod
    @abstractmethod
    def load(cls) -> ReactiveComponent:
        """Rebuild this component from the current world (zero-arg, type-singleton in v1)."""
        ...

    def state_hash(self) -> str:
        """
        Stable content hash of this component's state, used to gate OOB swaps so a
        region whose value did not change is not re-sent. Defaults to a hash of
        ``model_dump_json()``; override for custom hashing.
        """
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()[:16]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._pjx_reactive = True
        cls._pjx_reacts_to = frozenset(
            coerce_reactive_keys(getattr(cls, "reacts_to", None) or ())
        )
        cls._pjx_load_reads = frozenset(
            coerce_reactive_keys(getattr(cls, "load_reads", None) or ())
        )
        if "load" in cls.__dict__ and not cls._pjx_reacts_to:
            raise TypeError(
                f"{cls.__name__} defines load() but declares no reacts_to; a "
                f"reactive component must declare both."
            )
        if "load" in cls.__dict__:
            _load = cls.__dict__["load"]
            _func = _load.__func__ if isinstance(_load, classmethod) else _load
            cls._pjx_keyed = _load_param_count(_func) == 1
        if "load" in cls.__dict__:
            from .cache import install_cached_load

            install_cached_load(cls)


@dataclass
class _Candidate:
    """A dependency-matched region that has been reloaded and rendered."""

    id: str
    html: str
    fresh_hash: str
    reported_hash: str | None


def _parse_mounted(
    mounted: str | list[dict[str, Any]] | object | None,
) -> list[dict[str, Any]]:
    if mounted is None or mounted == "":
        return []
    if isinstance(mounted, list):
        return mounted
    if isinstance(mounted, str):
        try:
            parsed = json.loads(mounted)
        except json.JSONDecodeError:
            logger.warning(
                "Could not parse %s manifest as JSON; ignoring.", PJX_MOUNTED_HEADER
            )
            return []
        return parsed if isinstance(parsed, list) else []
    try:
        header_value = mounted.headers.get(PJX_MOUNTED_HEADER)
    except AttributeError:
        logger.warning(
            "mounted is not an %s header string, parsed list, request-like "
            "object, or None; ignoring.",
            PJX_MOUNTED_HEADER,
        )
        return []
    return _parse_mounted(header_value)


def parse_loaded_assets(
    client: str | list[str] | object | None,
) -> frozenset[str]:
    """
    Parse the client-reported list of asset URLs already loaded in the browser.

    Accepts a request-like object (``headers.get``), a raw JSON string, a parsed
    list of URLs, or ``None``/``""`` (treated as nothing loaded for dedup purposes).
    """
    if client is None or client == "":
        return frozenset()
    if isinstance(client, (list, tuple, set, frozenset)):
        return frozenset(str(url) for url in client)
    if isinstance(client, str):
        try:
            parsed = json.loads(client)
        except json.JSONDecodeError:
            logger.warning(
                "Could not parse %s as JSON; ignoring.", PJX_ASSETS_HEADER
            )
            return frozenset()
        if isinstance(parsed, list):
            return frozenset(str(url) for url in parsed)
        return frozenset()
    try:
        header_value = client.headers.get(PJX_ASSETS_HEADER)
    except AttributeError:
        return frozenset()
    return parse_loaded_assets(header_value)


def _drop_nested(candidates: list[_Candidate]) -> list[_Candidate]:
    """
    Drop any candidate whose data-pjx-id marker appears inside another candidate's
    HTML — the parent's fresh HTML already contains the child, so a separate swap
    would be redundant (and would fight the parent's swap).

    Runs only over regions that are actually being swapped (post hash-gate), so an
    unchanged parent never suppresses a changed child.
    """
    surviving: list[_Candidate] = []
    for index, candidate in enumerate(candidates):
        marker = f'data-pjx-id="{candidate.id}"'
        nested_in_other = any(
            marker in other.html
            for other_index, other in enumerate(candidates)
            if other_index != index
        )
        if not nested_in_other:
            surviving.append(candidate)
    return surviving


def oob_swaps(
    dirtied: set[ReactiveKey],
    mounted: str | list[dict[str, Any]] | object | None,
    *,
    exclude_ids: set[str] | None = None,
) -> Markup:
    """
    Compute out-of-band swap fragments for every mounted reactive region whose
    declared dependencies intersect the dirtied state keys.

    Dependency-filtered and hash-gated (issue #12, implementation order steps
    1-2): a region depending on a dirtied key is reloaded, and an OOB swap is
    emitted only if its freshly computed state hash differs from the hash the
    client reported for it. A matching hash earns permission to skip; a missing
    or mismatched hash always swaps ("when in doubt, swap").

    Args:
        dirtied: The state keys the route mutated (e.g. {"todos"}). These keys are
            also evicted from the process-global load() cache before dependents are
            reloaded.
        mounted: The client manifest — a request-like object exposing
            ``.headers.get`` (the X-PJX-Mounted header is duck-typed out without
            importing any web framework), the raw header string, an already-parsed
            list of {"id", "type", "hash"} dicts, or None/"".
        exclude_ids: Mounted ids to skip (e.g. the id of the primary response,
            which is swapped into the main target rather than out-of-band).

    Returns:
        A single Markup of concatenated OOB swap fragments, each carrying
        hx-swap-oob. Empty Markup if nothing needs swapping.
    """
    dirtied_keys = coerce_reactive_keys(dirtied)
    invalidate(dirtied_keys)

    manifest = _parse_mounted(mounted)
    if not manifest:
        return Markup("")

    classes = Registry.get_classes()
    renderer = Renderer.get_default_renderer()

    candidates: list[_Candidate] = []
    seen: set[tuple[str, str | None]] = set()
    for entry in manifest:
        component_type = entry.get("type")
        component_id = entry.get("id")
        key = entry.get("key")
        skey = str(key) if key is not None else None
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
        if keyed and skey is None:
            continue
        if not keyed:
            skey = None

        effective = interpolate_reactive_keys(
            getattr(component_class, "_pjx_reacts_to", frozenset()),
            skey,
            keyed=keyed,
        )
        if not (effective & dirtied_keys):
            continue

        dedup_key = (component_type, skey)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        instance = component_class.load(skey) if keyed else component_class.load()
        instance.id = component_id
        html = str(instance._render(_renderer=renderer, emit_assets=False))
        candidates.append(
            _Candidate(
                id=component_id,
                html=html,
                fresh_hash=instance.state_hash(),
                reported_hash=entry.get("hash"),
            )
        )

    changed = [c for c in candidates if c.fresh_hash != c.reported_hash]

    surviving = _drop_nested(changed)
    if not surviving:
        return Markup("")

    fragments = [
        stamp_root_attributes(
            c.html, {"hx-swap-oob": f"outerHTML:[data-pjx-id='{c.id}']"}
        )
        for c in surviving
    ]
    return Markup("\n".join(fragments))
