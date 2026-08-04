# Cache & Invalidation

The reactive `load()` cache and its cross-process fan-out.

!!! warning "Internal module"
    Nothing on this page is part of the public API — `pyjinhx.reactive.cache` and
    `pyjinhx.session` are absent from `pyjinhx.__all__` and their module paths may change.
    In normal use the cache is invisible: `setup(app)` scopes it and `@mutates` evicts
    from it. This page is for when you need to reach in anyway.

See [Reactivity](../reactivity.md) for usage patterns.

## Cache scope

The load cache is request-scoped: entries live in the dict the request scope (`request_scope()`, in the internal `pyjinhx.session`) hands out per request, and vanish when the scope exits. `pyjinhx.reactive.cache` owns no state of its own — it reads and writes through the session's store.

## make_key / cache_get / cache_has

```python
def make_key(cls: type, key: object) -> tuple[type, object]
def cache_get(cls: type, key: object) -> object | None
def cache_has(cls: type, key: object) -> bool
```

`make_key()` builds the composite `(cls, key)` cache key for a component class and a load key. `cache_get()` returns the cached value for a class and key, or `None` on a miss — including every lookup made outside an active request scope. Because a legitimately cached `None` is indistinguishable from a miss, use `cache_has()` when that distinction matters.

## cache_put

```python
def cache_put(
    cls: type, key: object, value: object, react_keys: Iterable[str] = ()
) -> None
```

Cache a load result for this class and key, replacing any existing entry. `react_keys` are the normalized reactive keys this result depends on — dirtying any of them evicts the entry. The default of no keys makes the entry plain memoization that only a fresh request clears. This is the only function that mutates the cache store, and is called automatically by the reactive `load()` memo wrap — not by application code directly.

## invalidate

```python
def invalidate(dirtied_keys: Iterable[str]) -> None
```

Evict every cache entry that depends on any of the given reactive keys. `@mutates` and `dirty()` do not call it — they only record the dirtied keys on the request. Eviction happens once, in `pyjinhx.responses.compose()`, which calls `invalidate(get_dirtied())` immediately before walking the manifest (see [Response composition](responses.md)). Evicting before the walk is what makes the walk honest: `walk_manifest()` reads the load cache to decide clean vs dirty, so an entry left in place would answer "clean" for data this request just changed. Outside a request scope this is a silent no-op, like the rest of the module.

## Cross-process fan-out

`pyjinhx.reactive.fanout` walks a client's `X-PJX-Mounted` manifest against a request's dirtied keys and decides, per mounted region, whether it is clean, dirty, or missing — driving the out-of-band (OOB) swaps `compose()` attaches to the response body. Its core entry points:

```python
def walk_manifest(
    manifest_entries: Sequence[dict[str, Any]],
    dirtied_keys: Iterable[str],
    session: RenderSession | None = None,
    primary_html: object = None,
) -> list[FanoutCandidate]

def oob_swaps(candidates: list[FanoutCandidate]) -> Markup
```

`walk_manifest()` resolves each manifest entry to a `FanoutCandidate`, re-rendering the ones a dirtied key touches; `oob_swaps()` assembles the surviving candidates' fragments into one response body (`outerHTML:` swaps for dirty regions, `delete:` swaps for regions that are gone).

### What counts as "gone"

A `delete:` swap is emitted for exactly one reason: the candidate's `load()` raised `LookupError`. A miss in the request-scoped instance registry is *not* that signal — the registry only holds instances this request rendered, so every region outside the primary tree misses it as a matter of course.

That makes raising part of `load()`'s contract. `KeyError` and `IndexError` both subclass `LookupError`, so an ordinary dict or list lookup against the app's own store is already the right thing:

```python
@classmethod
def load(cls, todo_id: int) -> "ItemRow":
    todo = store.todos[todo_id]  # KeyError -> LookupError -> delete swap
    return cls(id=f"todo-{todo_id}", todo_id=todo_id, text=todo.text)
```

A `load()` that catches the store's `KeyError` and returns a field-default instance instead swaps the region with a *blank* render rather than deleting it — the failure is silent and looks like an emptied region on the client.

This fan-out is in-process only — there is currently no built-in mechanism for propagating invalidation across worker processes or machines. Each worker's cache and registry are independent.
