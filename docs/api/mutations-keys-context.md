# Mutations, Keys & PjxContext

Public API for reactive state keys, mutation tracking, request-scoped load context, and development guardrails.

See [Reactivity](../reactivity.md) for conceptual documentation.

## MutationKey

```python
class MutationKey(StrEnum):
    ...
```

Base class for app-level reactive key constants. Subclass and declare members; use the members in `react={...}` and `@mutates` — all normalize to their string values. Both `react=` and `@mutates` only accept `MutationKey` members; passing a bare string raises `TypeError`.

```python
from pyjinhx import MutationKey

class Keys(MutationKey):
    TODOS = "todos"
```

## PjxKey

```python
class PjxKey:
    ...
```

Marker for `Annotated[..., PjxKey()]`. Keyed components declare exactly one `PjxKey` field; its value is stamped as `data-pjx-load` on render and returned in the client manifest as `load` for OOB `load()` round-trip.

```python
from typing import Annotated
from pyjinhx import MutationKey, PjxKey, ReactiveComponent

class Keys(MutationKey):
    TODOS = "todos"

class ItemRow(ReactiveComponent, react={Keys.TODOS}):
    todo_id: Annotated[int, PjxKey()]

    @classmethod
    def load(cls, todo_id: int | str) -> "ItemRow":
        # The cache wrapper passes the key as a string; convert before use.
        resolved_id = int(todo_id)
        ...
```

## mutates

```python
def mutates(*keys: MutationKey) -> Callable[[F], F]
```

Decorator for store mutation methods. Each arg must be a **`MutationKey` member** — bare strings raise `TypeError` at decoration time. After the wrapped function returns, invalidates the load cache and accumulates pending dirtied keys for the next reactive `render()`.

```python
from pyjinhx import MutationKey, mutates

class Keys(MutationKey):
    TODOS = "todos"

class Store:
    @mutates(Keys.TODOS)
    def add(self, text: str) -> None:
        ...
```

## dirty

```python
def dirty(*keys: MutationKey) -> None
```

Imperatively dirty reactive keys — the same effect `@mutates` has, but without decorating a function. Each arg must be a **`MutationKey` member** — bare strings raise `TypeError`. Invalidates the load cache and accumulates pending dirtied keys for the next reactive `render()`. A no-arg call is a no-op.

```python
from pyjinhx import MutationKey, dirty

class Keys(MutationKey):
    TODOS = "todos"

store.add_without_decorator(text)
dirty(Keys.TODOS)
```

## PjxContext

```python
@dataclass(frozen=True)
class PjxContext:
    ...
```

Opaque base for request-scoped data available inside reactive `load()` and any component method that declares a `PjxContext` parameter. Subclass with your own frozen dataclass fields (database session, user id, feature flags).

## PjxContext.current / PjxContext.bind

```python
PjxContext.current() -> Any | None
PjxContext.bind(ctx) -> ContextManager[None]
```

Return or set the load context for the current scope. Any component method that declares a parameter annotated with `PjxContext` (or a subclass) — including reactive `load()` — receives the current context when the parameter is left unbound; an explicitly passed argument takes precedence. At most one such parameter is allowed per method.

Prefer `Registry.request_scope(load_context=ctx)` in web apps — it combines registry isolation, request cache, mutation tracking, and load context in one call.

```python
from pyjinhx import PjxContext, Registry
from pyjinhx.integrations.fastapi import FastAPIClientBackend

@dataclass(frozen=True)
class AppLoadContext(PjxContext):
    db: Session

with Registry.request_scope(
    load_context=AppLoadContext(db=session),
    client_backend=FastAPIClientBackend(request),
):
    html = TodoList.render()
```

## Reactive dev

Development-time guardrails for catching common reactive mistakes.

### enable_reactive_dev

```python
def enable_reactive_dev(*, strict: bool = False) -> None
```

Enable guardrails. When enabled:

- Warns if `@mutates` recorded dirtied keys but no reactive `render()` consumed them in the request scope.
- Warns if mutations are pending but no `ClientBackend` is active (OOB swaps skipped).

Set `strict=True` to raise `RuntimeError` instead of logging warnings.

### disable_reactive_dev

```python
def disable_reactive_dev() -> None
```

Disable all dev guardrails.

### dependency_graph

```python
def dependency_graph() -> dict[str, list[str]]
```

Map each declared reactive key to the component class names that depend on it.

### format_dependency_graph

```python
def format_dependency_graph(*, as_mermaid: bool = False) -> str
```

Format the dependency graph as a text table or Mermaid flowchart. Useful for debugging and documentation.

```python
from pyjinhx.dev import format_dependency_graph

print(format_dependency_graph())
print(format_dependency_graph(as_mermaid=True))
```
