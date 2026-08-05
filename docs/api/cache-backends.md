# Cache Backends

The cross-request cache tier: what `load()` results and rendered levels are reused for, and what that costs when it is wrong.

!!! warning "Internal module"
    Nothing on this page is part of the public API — `pyjinhx.reactive.backend`, `pyjinhx.render_cache` and `pyjinhx.integrations.diskcache` are absent from `pyjinhx.__all__` and their module paths may change. The one thing an app touches deliberately is `setup(app, cache_backend=...)` and the `cache=` class keyword; everything below it is described so the behaviour those two switch on is legible, not so it can be called directly.

See [Cache & Invalidation](cache-invalidation.md) for tier 1, which is on always and needs no configuration.

## Two tiers

Tier 1 is the request-scoped `load()` memo. It lives in the dict `request_scope()` hands out, absorbs repeat lookups inside one request, and vanishes when the request ends — which makes it self-healing: a wrong entry cannot outlive the response that produced it.

Tier 2 is a `CacheBackend`. It is off unless an app configures one, and when it is on it spans requests — every request in this process, and with `DiskCacheBackend` every worker process on this machine. Nothing about it heals itself, which is why every entry carries a TTL.

The lookup path for a reactive `load()`:

1. Tier 1 hit → return it.
2. Tier 1 miss → ask tier 2. Hit → **promote into tier 1**, then return it. The promotion is what keeps tier 2's per-hit deserialization off the hot path for the rest of this request.
3. Tier 2 miss → call the real `load()` → write through to **both** tiers.

```
  cls.load(todo_id=3)
        │
        ▼
  ┌──────────────────────────────────────────────┐
  │ tier 1: request store  (cache_get/cache_put) │  ContextVar, per request
  │   hit ─────────────────────────────────► return
  └──────────────────────────────────────────────┘
        │ miss
        ▼
  ┌──────────────────────────────────────────────┐
  │ tier 2: CacheBackend   (get/put/evict)       │  process- or host-wide
  │   hit ── promote into tier 1 ───────────► return
  └──────────────────────────────────────────────┘
        │ miss
        ▼
  real load()  ──►  write through to BOTH tiers
```

## The backend protocol

```python
class CacheBackend(Protocol):
    def get(self, key: str) -> object
    def put(self, key: str, value: object, *, tags: Iterable[str], ttl: float | None) -> None
    def evict(self, tags: Iterable[str]) -> None
    def clear(self) -> None
```

Conformance is structural — anything with those four methods is a backend, and `isinstance(x, CacheBackend)` says so.

`get()` answers the module's `MISS` sentinel, not `None`, when there is no live entry: a `load()` may legitimately return and cache a falsy or `None`-valued component, and a caller has to be able to tell a cached `None` from an absent one.

Eviction is by tag rather than through a reverse index the caller keeps, because a store behind a disk file or a socket cannot expose one. The reactive keys tier 1 already indexes on (`"todos"`, `"todos:3"`) become the tags verbatim.

`InMemoryCacheBackend` is the reference implementation, in the same module. It holds values by reference — nothing is pickled or copied — which makes it useful for tests and for a single-process app that wants tier-2 semantics without a storage dependency, and useless for sharing anything across workers.

## Turning it on

```python
from pyjinhx import setup
from pyjinhx.integrations.diskcache import DiskCacheBackend

setup(app, cache_backend=DiskCacheBackend("/cache/pjx"))
```

The directory must be ephemeral per deployment — see [The cache is volatile](#the-cache-is-volatile) for why, and for the mount that gives you one on each platform.

`PjxSettings.cache_backend` defaults to `None`: no backend, no behaviour change, no new dependency. The backend is constructed by the app rather than named by a string in an environment variable — it needs a path or a connection, and the app is the only thing that knows them. `shutdown_pyjinhx()` calls `close()` on it if it has one.

**Configuring a backend turns tier 2 on for every component**, at `ttl=300`. There is no per-class opt-in to forget and no configuration where a backend is present but inert.

`CachePolicy` is how a class overrides that default, not how it earns it — and it reuses the `react=`-style class keyword, so the knob sits where the reactive contract already lives:

```python
class ItemRow(ReactiveComponent, react={Keys.TODOS}, cache=CachePolicy(ttl=60)): ...


class Feed(ReactiveComponent, react={Keys.POSTS}, cache=False):  # tier 1 only
    ...
```

`cache=CachePolicy(...)` and `cache=False` are the only per-class overrides. The keyword is set on every subclass rather than inherited: a subclass that silently picked up a parent's policy would be cached against state it never declared. With no backend configured, `cache=` is inert.

## Load cache (tier 2)

The reactive `load()` memo. The cached value is the `ReactiveComponent` instance `load()` returned, keyed on a string:

```
  (ItemRow, 3)  ──►  "pjx:1:myapp.rows.ItemRow:3"
                       │   │  │                 └── the load key, serialized
                       │   │  └── cls.__module__ + "." + cls.__qualname__
                       │   └── key-schema version, so an upgraded pyjinhx never
                       │       serves entries written under older semantics
                       └── namespace
```

Tier 1 keys on the live `(cls, key)` tuple; a class object cannot cross a process boundary, so tier 2 keys on this string, derived from the same value tier 1 uses. The two tiers cannot disagree about what identifies a call.

Under `extra="allow"` (protocol mode) the key covers every bound argument rather than one key field, serialized in sorted order and hashed once it gets long. A class whose load parameters do not serialize deterministically is refused at class-definition time — an argument whose `repr()` carries a memory address would key two equal calls apart and two different calls together, which is a wrong cache rather than a slow one.

Entries are tagged with the class's reactive keys plus, when the call has a load key, the `"todos:3"` composites `reactive_key()` produces — both forms, because `@mutates(key=...)` and `dirty(reactive_key(...))` dirty only the composite while a bare `dirty("todos")` dirties the plain one.

Eviction is one call. `invalidate(dirtied_keys)` sweeps tier 1's reverse index and then hands the very same keys to `backend.evict(tags)`; the dirtied keys are the tags verbatim, so there is no second index to maintain and nothing to translate. `@mutates` and `dirty()` do not call it themselves — they record dirtied keys, and `compose()` evicts once, before walking the manifest.

## Render cache (tier 2)

The other half, for the components the load cache cannot reach: a shell or layout that is re-rendered identically on every request is the more common waste, and it has no `load()` at all.

What is cached is the component's `RenderedLevel` with its child holes still unresolved, so this request's children splice into it normally on a hit. The key has three parts:

```
  myapp.shell.PageShell:<sha256 of model_dump()>:<template mtime>
```

— the fully qualified class name, a SHA-256 digest of the instance's own field values, and the modification time of the template the class resolved to (so an author's template edit invalidates the entry without a restart). Slot and children fields whose live value is a component are left out of the digest: those render as opaque holes and are spliced back in, so hashing them would make the key vary per request and never hit for the shell that is the point. The same field holding a plain *string* stays in the key, because that string is baked into the cached segments as text.

Two classes of instance are declined outright rather than cached wrong:

- **Reactive components.** A reactive class caches its `load()` result across requests already; caching its rendered shell too would key one component against two independently invalidated stores.
- **An instance holding a component in a slot or children field.** Its slot tokens are only valid for the one `template.render()` call that emitted them, and a cache hit performs no such call. This is answered per instance, not per class — the same `Slot` field holding a plain string is fine.

Entries are **untagged**. Tags exist so a dirtied reactive key can evict what it invalidated, and a non-reactive component has no reactive key behind it. Its only invalidation paths are a key change (props or template edit) and the TTL.

!!! danger "A render-cached component must be a function of its own fields"
    This is a correctness rule, not a style note. If a component's rendered output depends on anything outside its own fields — a module-level global, wall-clock time, request or session state, the current user — then two requests that differ only in that hidden input produce the same cache key, and the second one is served the first one's HTML until the TTL runs out. Nothing detects this: the key is derived from `model_dump()`, and what is not in the fields is not in the key.

    `cache=False` on the class is how such a component opts out.

A hit skips `render_level()`, and with it the fan-out that normally collects the descriptor's CSS and JS paths — so the restored level's asset paths are replayed into the session on every hit. Without that a cached page ships unstyled.

## Why the TTL is not optional

Tier 1 is self-healing: the request ends and the lie is gone. Tier 2 is not. Anything that mutates data *without* going through `dirty()`/`@mutates` — a cron job, a second service, a manual `UPDATE` — leaves an entry that is now wrong, and with a disk-backed store that entry outlives the restart, and the deploy, that would have cleared it.

So `CachePolicy.ttl` defaults to a finite `300` seconds, and `ttl=None` has to be written out:

```python
class Countries(
    ReactiveComponent, react={Keys.COUNTRIES}, cache=CachePolicy(ttl=None)
): ...
```

That is a safety net for correctness rather than a tuning knob, and it matters more under an on-by-default tier 2 than it would under an opt-in one.

## The cache is volatile

The store starts empty on every boot, and that is deliberate. A disk-backed cache is persistent by nature, and here the persistence is a hazard: a deploy that changes how a component loads or renders would otherwise serve output built by the previous version of the code, with the TTL bounding how long rather than preventing it.

The contract, then: **the directory you hand `DiskCacheBackend` must be ephemeral per deployment** — created empty when the deployment starts, gone when it stops. A path that survives a deploy is a misconfiguration, not a tuning choice. `DiskCacheBackend(directory)` takes that path as a required positional with no default precisely so the decision has to be made rather than inherited.

The one constraint on "empty" is that it means once per deployment, not once per worker: all workers share the store, and a worker booting into a running deployment must not wipe what its siblings warmed.

### The recipe, per platform

Every platform has a native mechanism that gives exactly this — a directory that is new and empty per deployment and shared by every worker inside it:

| Platform | Mechanism | Mount at |
| --- | --- | --- |
| Kubernetes | an `emptyDir` volume — new and empty per pod | `/cache` |
| Docker | `--tmpfs /cache` — a new tmpfs per container | `/cache` |
| systemd | `RuntimeDirectory=myapp` — created at start, removed at stop | `/run/myapp` |
| bare metal | any path under tmpfs | `/run/myapp/cache` |

Kubernetes:

```yaml
spec:
  containers:
    - name: web
      volumeMounts:
        - name: pjx-cache
          mountPath: /cache
  volumes:
    - name: pjx-cache
      emptyDir:
        medium: Memory
```

Docker:

```
docker run --tmpfs /cache myapp
```

systemd:

```ini
[Service]
RuntimeDirectory=myapp
```

Either way the app names the same path it was given:

```python
setup(app, cache_backend=DiskCacheBackend("/cache/pjx"))
```

The store is then empty on boot **by construction** — no wipe, no marker file, no supervisor detection — and workers still share it, because they share the pod or the container.

### Why this is the operator's job

Not an oversight: pyjinhx cannot do it correctly, and the reason is structural.

"App startup" is not one event. It is N events, one per worker, at times nobody controls. A wipe on startup either erases what sibling workers just warmed — including when a single worker respawns mid-life under live traffic — or it avoids that by giving each worker its own namespace, which throws away the cross-worker invalidation the shared store exists for.

Detecting "I am the first worker of a fresh boot" would need supervisor identity that no worker can reliably obtain. Hooking uvicorn's lifespan misses `gunicorn -k UvicornWorker` entirely, and parent-process identity is stable across restarts for single-process and `--reload` deployments, so it cannot distinguish a new boot from a respawn.

Nor is there a runtime warning to be had. A non-empty store at first use is indistinguishable from a sibling worker having warmed it a second earlier, so a warning would fire constantly on correct deployments and get muted, which is worse than none.

### What a persistent path costs

Stale output served across a deploy. Change a component's `load()` or its template, ship it, and requests are answered from entries the previous version wrote — correct-looking HTML built by code that no longer exists. Nothing in the key notices: the load key covers the call's arguments, and the render key covers the instance's fields and the template's mtime, neither of which changes when the *Python* changes. The TTL is the only thing that ends it, so the window is up to `CachePolicy.ttl` after every deploy — 300 seconds by default, unbounded under `ttl=None`.

Stated outright: the disk backend buys **cross-worker sharing, not warm start**. Every deploy begins cold, by design.

## DiskCacheBackend

```python
DiskCacheBackend(directory: str | Path, *, shards: int = 8, timeout: float = 0.010)
```

Ships as `pyjinhx[diskcache]`, in `pyjinhx.integrations.diskcache`. Nothing in `pyjinhx` imports it eagerly, so the extra stays optional.

- **`FanoutCache`, not `Cache`.** SQLite takes a database-level write lock, so a single database serializes every worker behind it; `FanoutCache` shards across several database files instead. `timeout` is how long one shard operation waits on that lock before giving up on that operation.
- **Cross-process invalidation comes free.** One directory, N connections: worker 1's `evict("todos")` is visible to workers 2..N on their next read. This is the property a module-level dict cannot have.
- **The tag index lives in the cache.** diskcache's native `tag=` field holds one tag per entry, and the protocol's entries carry several — so membership is kept as entries of the cache's own, under the reserved `pjx:diskcache:keys-of-tag:` and `pjx:diskcache:tags-of-key:` prefixes. In the cache rather than in a dict on the instance, because the whole point is that *another worker's* `evict()` finds them. Do not write keys under a `pjx:diskcache:` prefix into a cache pyjinhx is sharing.
- **One machine, not one cluster.** It is a shared *filesystem*, so the sharing holds for workers on a box. Four pods have four independent caches, and an eviction on one is invisible to the other three. That is the honest boundary, and it is where a Redis backend would earn its place — none ships, and the protocol is shaped to admit one.
- **Never over NFS.** SQLite's locking is unreliable over network filesystems, and a cache that corrupts under concurrency is worse than no cache. This is documented rather than detected: the check would be a guess about a mount point.

Values are pickled on the way in, so what `get()` answers is a copy of what `put()` was handed rather than the same object.

## When a component will not pickle

Pydantic models pickle, so an ordinary component round-trips — but not one holding a database handle, an open file, or a lambda in a field.

Because tier 2 is on for everything the moment a backend is configured, meeting such an instance is a *normal* condition rather than an authoring error. `put()` catches `pickle.PicklingError`, `TypeError` and `AttributeError`, logs once per class, and skips the entry. The component keeps working through tier 1, and the request is unaffected. A log line naming a class you know cannot pickle is not a bug report; `cache=False` on that class says so deliberately and silences it.

## When the backend itself fails

A cache is an optimization, so a backend that raises must not take a request down with it. What the failure costs depends on which call raised:

| Call | On failure | Degrades reads? |
| --- | --- | --- |
| `get()` | Treated as a miss; the work runs | No |
| `put()` | Write dropped; the next request pays for it | No |
| `evict()` | Entries that are now known to be wrong survive | **Yes** |

The first two cost speed. A dropped eviction costs correctness, so an `evict()` that raises marks that backend **degraded**: its `get()` is not consulted at all until a write lands, at which point the flag clears and it is trusted again.

Either way the failure is logged once per backend per process, not once per call — a backend that is down fails on every request, and a line per request buries the first one.

## What this does not solve

`load()` still runs on every miss, and a miss is the only way to discover that the data was unchanged. There is no cheap staleness probe distinct from calling `load()` itself — no version column, no `MAX(updated_at)` check. Adding one would mean a second author-supplied hook, and it is a separate design.

So: this removes repeated work for data that has genuinely not been dirtied. It does not let a component skip `load()` to find out *whether* it was dirtied.
