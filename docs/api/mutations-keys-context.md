# Mutations, Keys & LoadContext

Public API for reactive state keys, mutation tracking, request-scoped load context, and development guardrails.

See [Reactivity](../reactivity.md) for conceptual documentation.

## StateKey

```python
class StateKey(StrEnum):
    ...
```

Base class for app-level reactive key constants. Subclass and declare members; use the enum in `reacts_to` and `@mutates` — all normalize to their string values.

```python
from pyjinhx import StateKey

class Keys(StateKey):
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
from pyjinhx import PjxKey, ReactiveComponent

class ItemRow(ReactiveComponent):
    todo_id: Annotated[int, PjxKey()]
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls, todo_id: int) -> "ItemRow":
        ...
```

## mutates

```python
def mutates(*keys: ReactiveKey) -> Callable[[F], F]
```

Decorator for store mutation methods. Each arg is a **state key** (string or `StateKey` enum). After the wrapped function returns, invalidates the load cache and accumulates pending dirtied keys for the next reactive `render()`.

```python
from pyjinhx import mutates

class Store:
    @mutates("todos")
    def add(self, text: str) -> None:
        ...
```

## LoadContext

```python
@dataclass(frozen=True)
class LoadContext:
    ...
```

Opaque base for request-scoped data available inside reactive `load()`. Subclass with your own frozen dataclass fields (database session, user id, feature flags).

## LoadContext.current / LoadContext.bind

```python
LoadContext.current() -> Any | None
LoadContext.bind(ctx) -> ContextManager[None]
```

Return or set the load context for the current scope. Reactive `load()` methods receive a parameter annotated with `LoadContext` (or a subclass) when the context is set.

Prefer `Registry.request_scope(load_context=ctx)` in web apps — it combines registry isolation, request cache, mutation tracking, and load context in one call.

```python
from pyjinhx import LoadContext, Registry
from pyjinhx.integrations.fastapi import FastAPIClientBackend

@dataclass(frozen=True)
class AppLoadContext(LoadContext):
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
- Validates that `depends_on()` is a subset of the static `reacts_to` superset on each `load()`.

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
