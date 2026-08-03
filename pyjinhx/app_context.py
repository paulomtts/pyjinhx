"""AppContext: the marker an app's own context class subclasses to be injectable.

Import-pure on purpose - stdlib only, no pyjinhx imports - so the reactive
load() wrap can reach down into it from class-definition time without adding an
edge back into the render spine.

Deliberately not PjxContext: that class is the framework's own read-only view of
request state and is not meant to be subclassed by apps.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from types import UnionType
from typing import Any, Union, get_args, get_origin


class AppContext:
    """Base class for an app's per-request context object.

    Subclass it, return an instance from the ``context_factory`` passed to
    ``setup()``, and declare it on a component's ``load()``::

        class MyAppContext(AppContext):
            def __init__(self, db, user): ...

        class TodoList(ReactiveComponent):
            def load(self, ctx: MyAppContext): ...

    ``ctx`` is whatever that request's ``context_factory`` returned. With no
    factory configured - or when ``load()`` is called outside a request scope -
    it is ``None`` rather than an error, because a class is defined long before
    any app wiring exists to check against.
    """


def _is_app_context(annotation: Any) -> bool:
    """Report whether an annotation names an AppContext subclass.

    ``MyAppContext | None`` counts: an optional context is still a declared
    dependency on the same class, so the union is unwrapped and each member
    tested.
    """
    if isinstance(annotation, type):
        return issubclass(annotation, AppContext)
    if get_origin(annotation) in (Union, UnionType):
        return any(_is_app_context(arg) for arg in get_args(annotation))
    return False


def _param_hints(
    func: Callable[..., Any], parameters: Mapping[str, inspect.Parameter]
) -> dict[str, Any]:
    """Resolve only the parameter annotations, one at a time.

    ``get_type_hints(func)`` evaluates the return annotation too, and a factory
    ``load`` naturally returns its own class — a forward ref that does not
    resolve while that class is still being built (#713). Each parameter is
    resolved on its own so one unevaluable annotation drops only itself.
    """
    globalns = getattr(func, "__globals__", {})
    hints: dict[str, Any] = {}
    for name, param in parameters.items():
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            continue
        if isinstance(annotation, str):
            try:
                annotation = eval(annotation, globalns, None)
            except Exception:  # noqa: BLE001, S112 -- an unevaluable annotation is simply not a context
                continue
        hints[name] = annotation
    return hints


def resolve_load_context_param(func: Callable[..., Any]) -> str | None:
    """Return the name of ``func``'s app-context parameter, or None when it has none.

    Args:
        func: The unwrapped ``load`` function defined on a component class.

    Returns:
        The parameter name to pass the request's context under, or None when
        the signature declares no context parameter.

    Raises:
        TypeError: More than one parameter is annotated as an app context.
    """
    try:
        parameters = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return None
    hints = _param_hints(func, parameters)
    names = [
        name for name in parameters if name in hints and _is_app_context(hints[name])
    ]
    if not names:
        return None
    if len(names) > 1:
        raise TypeError(
            f"{getattr(func, '__qualname__', func)!r} declares multiple app-context "
            f"parameters {names!r}; at most one is allowed."
        )
    return names[0]
