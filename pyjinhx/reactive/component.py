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
from pyjinhx.reactive.keys import coerce_reactive_keys
from pyjinhx.utils import pascal_case_to_kebab_case


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

        from .render import _reactive_context_active, reactive_render_bundle

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
            from .render import _reactive_context_active, reactive_render_bundle

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

    reacts_to: ClassVar[set[str]] = set()
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
    def _load_param_count(func: Any, owner: type[Any] | None = None) -> int:
        """Count ``load()`` parameters excluding ``cls``, LoadContext params, and variadics."""
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
            from .context import resolve_load_context_param
            from .pjx_load import resolve_pjx_load_field, validate_pjx_load_subclass

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
            from .load_cache import LoadCache

            LoadCache.install_cached_load(cls)
