from __future__ import annotations

import hashlib
import inspect
from abc import abstractmethod
from collections.abc import Callable
from functools import partial
from typing import Any, ClassVar

from markupsafe import Markup
from pydantic import ConfigDict, PrivateAttr, model_validator

from pyjinhx.core.base import BaseComponent
from pyjinhx.utils import (
    ReactiveKey,
    coerce_load_key_str,
    coerce_reactive_keys,
    interpolate_reactive_keys,
    pascal_case_to_kebab_case,
)

from .cache import invalidate
from .client import oob_swaps


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
        from .backend import ClientBackend
        from .dev import warn_reactive_render_without_mounted
        from .mutations import mark_reactive_render_consumed, resolve_effective_dirtied

        resolved_mounted = ClientBackend.resolve_mounted(mounted, dirtied=dirtied)
        own_keys = interpolate_reactive_keys(
            getattr(cls, "_pjx_reacts_to", frozenset()), skey, keyed=keyed
        )
        warn_reactive_render_without_mounted(
            dirtied=dirtied, mounted=resolved_mounted, own_keys=own_keys
        )
        effective_dirtied = resolve_effective_dirtied(
            dirtied=dirtied,
            mounted=resolved_mounted,
            own_keys=own_keys,
        )
        invalidate(effective_dirtied | own_keys)
        instance = cls.load(skey) if keyed else cls.load()
        primary = instance._render(emit_assets=False)
        mark_reactive_render_consumed()
        swaps = oob_swaps(
            effective_dirtied, resolved_mounted, exclude_ids={instance.id}
        )
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
