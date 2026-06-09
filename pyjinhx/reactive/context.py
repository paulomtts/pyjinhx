from __future__ import annotations

import inspect
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from types import NoneType, UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

_load_context: ContextVar[Any | None] = ContextVar("load_context", default=None)


def _hint_namespace(owner: type[Any] | None, func: Callable[..., Any]) -> dict[str, Any]:
    module = sys.modules.get(func.__module__)
    globalns = dict(vars(module)) if module is not None else {}
    if owner is not None:
        globalns[owner.__name__] = owner
    globalns.setdefault("LoadContext", LoadContext)
    return globalns


def _resolved_hints(func: Callable[..., Any], owner: type[Any] | None = None) -> dict[str, Any]:
    try:
        return get_type_hints(func, globalns=_hint_namespace(owner, func), localns=None)
    except (NameError, TypeError, AttributeError):
        return {}


def _is_load_context_type(annotation: Any) -> bool:
    if annotation is inspect.Parameter.empty or annotation is None:
        return False

    origin = get_origin(annotation)
    if origin is not None:
        if origin in (Union, UnionType):
            return any(
                _is_load_context_type(arg) for arg in get_args(annotation) if arg is not NoneType
            )
        return False

    if annotation is LoadContext:
        return True

    if not isinstance(annotation, type):
        return False

    try:
        return issubclass(annotation, LoadContext)
    except TypeError:
        return False


def _is_load_context_param(
    param: inspect.Parameter,
    hints: dict[str, Any],
) -> bool:
    if param.name == "cls":
        return False
    annotation = hints.get(param.name, param.annotation)
    return _is_load_context_type(annotation)


def resolve_load_context_param(
    func: Callable[..., Any],
    owner: type[Any] | None = None,
) -> inspect.Parameter | None:
    """
    Return the single ``load()`` parameter annotated with ``LoadContext`` (or a
    subclass), or ``None`` when absent.

    Raises ``TypeError`` when more than one parameter carries that annotation.
    """
    signature = inspect.signature(func)
    hints = _resolved_hints(func, owner)
    matches = [
        param
        for param in signature.parameters.values()
        if _is_load_context_param(param, hints)
    ]
    if len(matches) > 1:
        names = ", ".join(param.name for param in matches)
        raise TypeError(
            f"{func.__qualname__} declares multiple LoadContext parameters "
            f"({names}); at most one is allowed."
        )
    return matches[0] if matches else None


def resolve_instance_key_param(
    func: Callable[..., Any],
    owner: type[Any] | None = None,
) -> inspect.Parameter | None:
    """Return the instance-key parameter, excluding ``cls`` and LoadContext params."""
    signature = inspect.signature(func)
    hints = _resolved_hints(func, owner)
    for param in signature.parameters.values():
        if param.name == "cls":
            continue
        if param.kind in (
            inspect.Parameter.VAR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        ):
            continue
        if _is_load_context_param(param, hints):
            continue
        return param
    return None


def invoke_raw_load(
    raw_func: Callable[..., Any],
    component_class: type[Any],
    *,
    key: str | None,
    ctx: Any | None,
    owner: type[Any] | None = None,
) -> Any:
    """Call a raw ``load()`` implementation, injecting bound LoadContext when declared."""
    signature = inspect.signature(raw_func)
    ctx_param = resolve_load_context_param(raw_func, owner)
    bind_kwargs: dict[str, Any] = {}
    if ctx_param is not None:
        bind_kwargs[ctx_param.name] = ctx
    if key is not None:
        key_param = resolve_instance_key_param(raw_func, owner)
        if key_param is None:
            raise TypeError(
                f"{raw_func.__qualname__} received an instance key but declares "
                f"no key parameter."
            )
        bind_kwargs[key_param.name] = key
    bound = signature.bind(component_class, **bind_kwargs)
    bound.apply_defaults()
    return raw_func(*bound.args, **bound.kwargs)


@dataclass(frozen=True)
class LoadContext:
    """
    Opaque base for request-scoped data available inside reactive ``load()``.

    Subclass or replace with your own frozen dataclass; set per request via
    ``LoadContext.bind()`` or ``Registry.request_scope(load_context=...)``.
    """

    @staticmethod
    def current() -> Any | None:
        """Return the current load context, or ``None`` outside a scope."""
        return _load_context.get()

    @staticmethod
    @contextmanager
    def bind(ctx: Any) -> Generator[None, None, None]:
        """Set the load context for the current scope."""
        token = _load_context.set(ctx)
        try:
            yield
        finally:
            _load_context.reset(token)
