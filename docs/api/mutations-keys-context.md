# Mutations, Keys & LoadContext

Public API for reactive state keys, mutation tracking, request-scoped load context, and development guardrails.

See [Reactivity](../reactivity.md) for conceptual documentation.

## StateKey

```python
class StateKey(StrEnum):
    ...
```

Base class for app-level reactive key constants. Subclass and declare members; use the enum in `reacts_to`, `dirtied`, and `@mutates` — all normalize to their string values.

```python
from pyjinhx import StateKey

class Keys(StateKey):
    TODOS = "todos"
    TODO = "todo"
```

## instance_key

```python
def instance_key(stem: str, key: str | int) -> str
```

Build an instance-tier dirty key.

```python
instance_key("todo", 42)  # "todo:42"
```

## dirty_keys

```python
def dirty_keys(instance_stem: str, key: str | int, *collection: ReactiveKey) -> set[str]
```

Build a two-tier dirty set for instance-keyed mutations. Returns the expanded instance key plus any collection-tier keys.

```python
dirty_keys("todo", 42, "todos")
# {"todo:42", "todos"}
```

Use with `mutation_scope()` when a mutation affects both a single row and a collection summary.

## mutates

```python
def mutates(*keys: ReactiveKey) -> Callable[[F], F]
```

Decorator for store mutation methods. After the wrapped function returns, invalidates the load cache for `keys` and accumulates them as pending dirtied for the next reactive `render()` when `dirtied` is omitted.

```python
from pyjinhx import mutates

class Store:
    @mutates("todos")
    def add(self, text: str) -> None:
        ...
```

## mutation_scope

```python
@contextmanager
def mutation_scope(*keys: ReactiveKey) -> Generator[None, None, None]
```

Context manager that invalidates and accumulates dirtied keys when the block exits (not on entry). Use for mutations that don't map cleanly to a single decorated method.

```python
from pyjinhx import dirty_keys, mutation_scope

with mutation_scope(*dirty_keys(Keys.TODO, todo_id, Keys.TODOS)):
    self._toggle(todo_id)
```

## LoadContext

```python
@dataclass(frozen=True)
class LoadContext:
    ...
```

Opaque base for request-scoped data available inside reactive `load()`. Subclass with your own frozen dataclass fields (database session, user id, feature flags).

## get_load_context

```python
def get_load_context() -> Any | None
```

Return the current load context, or `None` outside a scope. Reactive `load()` methods accept an optional keyword-only `ctx=` argument when the context is set.

## load_scope

```python
@contextmanager
def load_scope(ctx: Any) -> Generator[None, None, None]
```

Set the load context for the current scope. Prefer `Registry.request_scope(load_context=ctx)` in web apps — it combines registry isolation, request cache, mutation tracking, and load context in one call.

```python
from pyjinhx import LoadContext, Registry

@dataclass(frozen=True)
class AppLoadContext(LoadContext):
    db: Session

with Registry.request_scope(load_context=AppLoadContext(db=session)):
    html = TodoList.render(mounted=request)
```

## Reactive dev

Development-time guardrails for catching common reactive mistakes.

### enable_reactive_dev

```python
def enable_reactive_dev(*, strict: bool = False) -> None
```

Enable guardrails. When enabled:

- Warns if `@mutates` recorded dirtied keys but no reactive `render()` consumed them in the request scope.
- Warns if dirtied keys are set but `mounted` was not passed (OOB swaps skipped).
- Validates that `load_reads` keys are covered by `reacts_to` on each `load()`.

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

Map each declared reactive key to the component class names that depend on it. Instance-tier stems appear as declared (e.g. `"todo"`), not expanded per instance.

### format_dependency_graph

```python
def format_dependency_graph(*, as_mermaid: bool = False) -> str
```

Format the dependency graph as a text table or Mermaid flowchart. Useful for debugging and documentation.

```python
from pyjinhx import format_dependency_graph

print(format_dependency_graph())
print(format_dependency_graph(as_mermaid=True))
```
