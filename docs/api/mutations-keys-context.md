# Mutations, Keys & PjxContext

Public API for reactive state keys, mutation tracking, request-scoped load context, and development guardrails.

See [Reactivity](../reactivity.md) for conceptual documentation.

## MutationKey

```python
class MutationKey(StrEnum): ...
```

Base class for app-level reactive key constants. Subclass and declare members; use the members in `react={...}` and `@mutates` — all normalize to their string values. Both `react=` and `@mutates` only accept `MutationKey` members; passing a bare string raises `TypeError`.

```python
from pyjinhx import MutationKey


class Keys(MutationKey):
    TODOS = "todos"
```

## PjxKey

```python
class PjxKey: ...
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
def mutates(*keys: MutationKey, key: Callable[..., object] | None = None) -> Callable[[F], F]
```

Decorator for store mutation methods. Each arg must be a **`MutationKey` member** or a **`reactive_key()`** value — bare strings raise `TypeError` at decoration time. After the wrapped function returns, invalidates the load cache and accumulates pending dirtied keys for the next reactive `render()`.

```python
from pyjinhx import MutationKey, mutates


class Keys(MutationKey):
    TODOS = "todos"


class Store:
    @mutates(Keys.TODOS)
    def add(self, text: str) -> None: ...
```

Pass `key=` to derive a per-instance key instead of dirtying `keys` directly. It's called with the wrapped function's own arguments, and its return value feeds `reactive_key()` for every key in `keys` — dirtying only the one mounted instance whose load key matches, instead of every instance reacting to `Keys.TODO`:

```python
class Store:
    @mutates(Keys.TODO, key=lambda self, todo_id: todo_id)
    def toggle(self, todo_id: int) -> None: ...
```

## dirty

```python
def dirty(*keys: MutationKey | DynamicReactiveKey) -> None
```

Imperatively dirty reactive keys — the same effect `@mutates` has, but without decorating a function. Each arg must be a **`MutationKey` member** or a **`reactive_key()`** value — bare strings raise `TypeError`. Invalidates the load cache and accumulates pending dirtied keys for the next reactive `render()`. A no-arg call is a no-op.

```python
from pyjinhx import MutationKey, dirty


class Keys(MutationKey):
    TODOS = "todos"


store.add_without_decorator(text)
dirty(Keys.TODOS)
```

## reactive_key

```python
def reactive_key(key: MutationKey, arg: object) -> DynamicReactiveKey
```

Build a per-instance reactive key from a static `MutationKey` and an instance's own load key. Use the result with `dirty()` or `@mutates(key=...)` to invalidate/reload only the one mounted instance whose load key matches `arg`, instead of every instance reacting to `key`.

```python
from pyjinhx import MutationKey, dirty, reactive_key


class Keys(MutationKey):
    TODO = "todo"


dirty(reactive_key(Keys.TODO, todo_id))
```

### Injecting an app context into `load()`

An app's per-request context — a database session, the signed-in user, a
tenant — reaches a component by declaring it on `load()`:

```python
from typing import Self

from pyjinhx.app_context import AppContext
from pyjinhx.reactive.component import ReactiveComponent


class MyAppContext(AppContext):
    def __init__(self, db, user):
        self.db = db
        self.user = user


class TodoList(ReactiveComponent):
    items: list = []

    @classmethod
    def load(cls, ctx: MyAppContext | None = None) -> Self:
        return cls(items=ctx.db.todos_for(ctx.user) if ctx else [])
```

The value comes from the `context_factory` given to `setup()`, called once per
request with that request's `Request`:

```python
setup(app, context_factory=lambda request: MyAppContext(db=get_db(), user=request.user))
```

Rules:

- The context class must subclass `AppContext`. `PjxContext` is the framework's
  own read-only view of request state and is not subclassable for this.
- Matching is by type annotation, not by parameter name — call the parameter
  whatever reads best.
- `MyAppContext | None` is matched too, and is the honest annotation when the
  app may run without a factory.
- With no `context_factory` configured, or when `load()` runs outside a request
  scope, the parameter receives `None` rather than raising: a component class is
  defined at import time, long before any app wiring exists to validate against.
- At most one parameter may be annotated as an app context; two raise `TypeError`
  when the class is defined.
- A zero-argument `load(cls)` is untouched — no injection is attempted and
  nothing about its behavior changes.

## Reactive dev

Development-time guardrails for catching common reactive mistakes.

### enable_reactive_dev

```python
def enable_reactive_dev(*, strict: bool = False) -> None
```

Enable guardrails. When enabled:

- Warns if `@mutates` or `dirty()` recorded dirtied keys that no reactive `render()` consumed by the end of the request scope.

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
