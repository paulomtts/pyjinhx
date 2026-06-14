from __future__ import annotations

import functools
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
    globalns.setdefault("PjxContext", PjxContext)
    return globalns


def _resolved_hints(func: Callable[..., Any], owner: type[Any] | None = None) -> dict[str, Any]:
    try:
        return get_type_hints(func, globalns=_hint_namespace(owner, func), localns=None)
    except (NameError, TypeError, AttributeError):
        return {}


def _is_load_context(annotation: Any) -> bool:
    """True if ``annotation`` is ``PjxContext`` or a subclass, including ``X | None``."""
    if annotation is inspect.Parameter.empty or annotation is None:
        return False
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return any(
            _is_load_context(arg)
            for arg in get_args(annotation)
            if arg is not NoneType
        )
    if origin is not None:
        return False
    return isinstance(annotation, type) and issubclass(annotation, PjxContext)


def _is_load_context_param(param: inspect.Parameter, hints: dict[str, Any]) -> bool:
    if param.name == "cls":
        return False
    return _is_load_context(hints.get(param.name, param.annotation))


def resolve_load_context_param(
    func: Callable[..., Any],
    owner: type[Any] | None = None,
) -> inspect.Parameter | None:
    """
    Return the single ``load()`` parameter annotated with ``PjxContext`` (or a
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
            f"{func.__qualname__} declares multiple PjxContext parameters "
            f"({names}); at most one is allowed."
        )
    return matches[0] if matches else None


def resolve_instance_key_param(
    func: Callable[..., Any],
    owner: type[Any] | None = None,
) -> inspect.Parameter | None:
    """Return the instance-key parameter, excluding ``cls`` and PjxContext params."""
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
    """Call a raw ``load()`` implementation, injecting bound PjxContext when declared."""
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


def _make_context_wrapper(func: Callable[..., Any], ctx_name: str) -> Callable[..., Any]:
    """Wrap ``func`` so ``ctx_name`` is filled from ``PjxContext.current()`` when
    the caller leaves it unbound."""
    signature = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = signature.bind_partial(*args, **kwargs)
        if ctx_name not in bound.arguments:
            kwargs[ctx_name] = PjxContext.current()
        return func(*args, **kwargs)

    wrapper._pjx_ctx_injected = True  # type: ignore[attr-defined]
    return wrapper


def wrap_context_methods(cls: type[Any]) -> None:
    """Wrap each of ``cls``'s own methods declaring a single PjxContext parameter
    so the current load context is injected when left unbound.

    Handles instance methods, ``@classmethod`` and ``@staticmethod``. ``load`` is
    skipped — it keeps its dedicated injection path via
    ``LoadCache.install_cached_load``.
    """
    for name, attr in list(vars(cls).items()):
        if name == "load":
            continue
        if isinstance(attr, (classmethod, staticmethod)):
            func = attr.__func__
        elif inspect.isfunction(attr):
            func = attr
        else:
            continue
        if getattr(func, "_pjx_ctx_injected", False):
            continue
        ctx_param = resolve_load_context_param(func, cls)
        if ctx_param is None:
            continue
        wrapped = _make_context_wrapper(func, ctx_param.name)
        # ``func`` retains its leading ``self``/``cls`` arg; the descriptor re-wrap
        # below restores it, so ``bind_partial`` sees the same args as a raw call.
        if isinstance(attr, classmethod):
            wrapped = classmethod(wrapped)
        elif isinstance(attr, staticmethod):
            wrapped = staticmethod(wrapped)
        setattr(cls, name, wrapped)


@dataclass(frozen=True)
class PjxContext:
    """
    Opaque base for request-scoped data available inside reactive ``load()``.

    Subclass or replace with your own frozen dataclass; set per request via
    ``PjxContext.bind()`` or ``Registry.request_scope(load_context=...)``.
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
