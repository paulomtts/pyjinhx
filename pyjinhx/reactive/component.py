from __future__ import annotations

import hashlib
import inspect
import json
from abc import abstractmethod
from collections.abc import Callable
from functools import partial
from typing import Any, ClassVar

from markupsafe import Markup
from pydantic import ConfigDict, PrivateAttr, model_validator

from pyjinhx.core.base import BaseComponent
from pyjinhx.reactive.keys import (
    ReactiveKey,
    coerce_load_key_str,
    coerce_reactive_keys,
    interpolate_reactive_keys,
)
from pyjinhx.utils import pascal_case_to_kebab_case


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
        from .render import reactive_render_bundle

        resolved_mounted = ClientBackend.resolve_mounted(mounted, dirtied=dirtied)
        own_keys = interpolate_reactive_keys(
            getattr(cls, "_pjx_reacts_to", frozenset()), skey, keyed=keyed
        )
        loaded: list[ReactiveComponent] = []

        def build_primary() -> str:
            instance = cls.load(skey) if keyed else cls.load()
            loaded.append(instance)
            return instance._render(emit_assets=False)

        return reactive_render_bundle(
            primary_html=build_primary,
            own_keys=own_keys,
            dirtied=dirtied,
            mounted=resolved_mounted,
            exclude_ids=lambda: {loaded[0].id},
            invalidate_before_primary=True,
        )

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
    state_hash_exclude: ClassVar[frozenset[str]] = frozenset({"id"})

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

    @staticmethod
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

    def depends_on(self) -> set[str]:
        """
        Reactive keys this loaded instance currently depends on.

        Defaults to the interpolated static ``reacts_to`` declaration. Override to
        narrow (or expand, with dev warnings) based on instance state. The static
        ``reacts_to`` must remain a superset for cache-safety.
        """
        component_class = type(self)
        return interpolate_reactive_keys(
            getattr(component_class, "_pjx_reacts_to", frozenset()),
            self._pjx_key,
            keyed=getattr(component_class, "_pjx_keyed", False),
        )

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

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._pjx_reactive = True
        cls._pjx_reacts_to = frozenset(
            coerce_reactive_keys(getattr(cls, "reacts_to", None) or ())
        )
        if "load" in cls.__dict__ and not cls._pjx_reacts_to:
            raise TypeError(
                f"{cls.__name__} defines load() but declares no reacts_to; a "
                f"reactive component must declare both."
            )
        if "load" in cls.__dict__:
            _load = cls.__dict__["load"]
            _func = _load.__func__ if isinstance(_load, classmethod) else _load
            param_count = ReactiveComponent._load_param_count(_func)
            if param_count > 1:
                raise TypeError(
                    f"{cls.__name__}.load() has {param_count} key parameters; "
                    f"at most one instance key is supported."
                )
            cls._pjx_keyed = param_count == 1
        if "load" in cls.__dict__:
            from .load_cache import LoadCache

            LoadCache.install_cached_load(cls)
