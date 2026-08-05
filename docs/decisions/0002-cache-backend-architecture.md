# ADR 0002: Two-tier cache with a pluggable cross-request backend

**Status:** Accepted, 2026-08-05. Fulfills the deferral in rebuild ADR 0011 (`docs/superpowers/rebuild/adr/0011-process-decisions.md`, "Cross-request InvalidationBackend deferred post-1.0") and the deferred cache scope in rebuild ADR 0009 (`docs/superpowers/rebuild/adr/0009-minimal-instance-registry.md`, "Cache scope: request scope only, in L2" — resolved there as *deferred, not forbidden*). Shipped in 1.4.0.

## Context

Every request rebuilds every reactive component from scratch, even when nothing it depends on has changed since the last request. The request-scoped `LoadCache` (`pyjinhx/reactive/cache.py`) memoizes a `load()` result *within* one request — repeat lookups for the same `(class, key)` cost one call, not N — but `request_scope()` discards that store, the instance registry, and the dirtied set at the end of every request. Two consecutive requests for the same unchanged data both pay a full `load()`.

0011 named this gap and deferred it: "the Redis/SQLite cross-worker invalidation backends do not gate 1.0." 0009 named the same shape from the other side — "a process-wide cache is not a mandate" for L2 — and explicitly left the door open: "a later ADR can add process scope or cross-worker propagation as an additive change without reopening the enumeration." This is that ADR.

The naive fix — a module-level dict — fails immediately under more than one worker process: worker 1's `@mutates` evicts worker 1's copy, and workers 2..N keep serving what they cached. A cross-request cache that doesn't survive a multi-worker deployment isn't a cross-request cache in production.

## Decision: a second tier, not a replacement

The request-scoped `LoadCache` is unchanged and stays tier 1. A second tier sits behind it, addressed through a `CacheBackend` protocol — four methods, `get`/`put`/`evict`/`clear` — with tag-based eviction rather than a caller-maintained reverse index. The reactive keys tier 1 already indexes entries by become the backend's tags verbatim, so `invalidate()` gained one line and no new concept:

```
  cls.load(todo_id=3)
        │
        ▼  tier 1: request store           ContextVar, per request
        │ miss
        ▼  tier 2: CacheBackend            process- or host-wide
        │ miss                (hit → promote into tier 1)
        ▼
  real_load()  ──►  write through to both
```

Tier 1 absorbs repeat lookups within one request, which keeps tier 2's deserialization cost off the hot path — a render tree that mounts the same component twelve times still only reads tier 2 once.

**Rejected: replace tier 1 with tier 2.** Every lookup would pay a backend round-trip even for repeats inside the same request, for no benefit — nothing changes mid-request that tier 1's own invalidation doesn't already handle.

## Decision: string keys with a schema version

The request-scoped cache keys on `(cls, key)` — a live class object, which cannot cross a process boundary. The cross-request key is a versioned string instead:

```
  pjx:1:<module>.<qualname>:<load_key>
```

The version segment exists so a pyjinhx upgrade that changes key semantics cannot serve an entry built under the old ones; without it, a stale entry from before an upgrade would be read back as if it meant something under the new code.

## Decision: on by default once a backend is configured

**Configuring a backend turns tier 2 on for every reactive component**, at a default TTL, rather than requiring a per-class opt-in. `cache=CachePolicy(ttl=...)` overrides the TTL for a class; `cache=False` opts it out entirely.

**Rejected: opt-in per class.** The first design took this shape — `cache=CachePolicy(...)` was how a class *earned* caching, and a plain `react={...}` class got tier 1 only. Reversed because it puts the burden in the wrong place: an app with hundreds of reactive components would need every one annotated before a backend did anything, and the ones an author forgets are exactly the ones silently missing the benefit. On-by-default makes "configure a backend" a single, complete decision; the override exists for the narrower case of *disabling* it, not earning it.

This reversal has one direct consequence: a component holding something unpicklable (a database handle, an open file, a lambda in a field) is no longer an author error, because caching wasn't something the author opted into. It's a normal condition — see below.

## Decision: mandatory finite TTL

`CachePolicy.ttl` defaults to a finite value; `ttl=None` must be spelled explicitly. Tier 1 is self-healing — the request ends and a wrong entry is gone. A persistent tier 2 survives restarts, so anything that mutates data *without* going through `dirty()`/`@mutates` — a cron job, a second service, a manual `UPDATE` — leaves a wrong entry that outlives the deploy that would have cleared it. The TTL is a correctness backstop, not a tuning knob, and it matters more under on-by-default than it would have under opt-in.

## Decision: unpicklable values degrade, never raise

`put()` on a value that fails to pickle logs once per class and skips — the component keeps working through tier 1, nothing raises. This follows directly from on-by-default: since caching is no longer something an author chose, an instance that can't be cached is not a mistake to punish, it's a class the cache backend simply can't help. `cache=False` is how an author states the same thing deliberately and silences the log.

## Decision: cache directory ephemerality is the deployment's job, not the library's

The store must not outlive the process run that wrote it — a deploy that changes how a component loads or renders must not serve output built by the previous version of the code, with the TTL bounding how long rather than preventing it entirely.

**Rejected: an in-process wipe at startup.** "App startup" is not one event; it's N events, one per worker, at unpredictable times. A wipe on every worker's startup either erases what sibling workers already warmed — including when a single worker respawns mid-life under live traffic and wipes a fully-warm cache — or, to avoid that, gives each worker its own namespace, which breaks the cross-worker invalidation that justified a shared store in the first place.

**Rejected: detecting "first worker of a fresh boot."** No reliable signal exists across deployment topologies. Hooking the supervisor works for `uvicorn --workers N` (a real parent) but not `gunicorn -k UvicornWorker` (uvicorn *is* the worker; gunicorn is the parent). Parent-process identity is stable across restarts for a single-process deployment and for `--reload`, which is exactly when the cache most needs to die.

**Decision:** every deployment platform already solves "a directory that starts empty per deployment and is shared by every worker inside it" — a Kubernetes `emptyDir`, a Docker `--tmpfs`, a systemd `RuntimeDirectory=`. `DiskCacheBackend(directory)` takes the path as a required positional with no default, so the choice cannot be skipped by omission; making the directory ephemeral is documented as the operator's responsibility rather than detected or enforced, because a warm store at first use is indistinguishable from one a sibling worker just filled — any runtime check would fire constantly on correct deployments.

## Decision: the first concrete backend is disk-backed, local-machine only

`DiskCacheBackend` stores entries in SQLite (`FanoutCache`, sharded so N workers writing do not serialize behind one write lock). This is a **one-machine cache, not a one-cluster one**: workers sharing a filesystem share a store; four Kubernetes pods have four independent caches. Local disk only — SQLite's locking is unreliable over NFS, and a cache that corrupts under concurrency is worse than no cache.

A Redis backend, for cross-host sharing, is deliberately not built. The `CacheBackend` protocol is shaped to admit one as an ordinary implementation with no change above it — invalidation falls out of workers sharing one store, not a pub/sub channel beside it — but nothing forced building it now. The pre-1.4.0 `redis` extra, which named a `RedisInvalidationBackend` that never existed, was removed rather than left to imply otherwise.

## Decision: the same seam also caches non-reactive render output

A shell or layout has no `load()` and no reactive keys, but is re-rendered identically on every request — a form of waste the load cache cannot see at all. The same `CacheBackend` protocol, the same on-by-default rule, and the same `CachePolicy`/`cache=False` knobs extend to it, caching the `RenderedLevel` with its child holes still unresolved (so each request's children still splice in) rather than the finished HTML.

Two decisions specific to this half:

- **Invalidation is by key, not by tag.** A non-reactive component has no reactive keys to tag, so its cache key — class identity, a hash of its own field values, the template's content digest — *is* the content. A changed prop or template produces a different key; there is nothing to evict, only entries that age out under TTL.
- **Components too cheap to be worth caching are skipped, measured, not guessed.** A cache hit costs a key lookup, a backend read, an unpickle, and an asset-accumulation replay — roughly 20µs for a small component. Every builtin this repo ships renders in 31–105µs, and only a fraction of that is Jinja work a hit would actually save; caching them measured as a net loss (0.58–0.98× — slower with the cache than without). The render path times each class once — the template render and parse only, not the surrounding validation and child-filling a hit pays regardless — and remembers the verdict for the life of the process. The floor defaults to 150µs and reads `PJX_RENDER_CACHE_MIN_US`; an explicit `cache=CachePolicy(...)` overrides the measurement, so the field means one thing throughout the whole cache surface: `False` never, a policy always, absent lets the measurement decide.

## Consequences

- **Nothing changes until a backend is configured.** `PjxSettings.cache_backend` defaults to `None`; with none, every code path behaves exactly as it did in 1.3.0.
- **A configured backend is a per-process decision that reaches every reactive and non-reactive component at once**, not something threaded through a codebase class by class. The override knobs exist for exceptions, not for the common case.
- **The cache never outlives the deployment that populated it — as long as the operator honors the directory contract.** pyjinhx cannot enforce this and does not try; a persistent path is a misconfiguration the docs name explicitly rather than a state the library detects.
- **This buys cross-worker sharing, not warm start.** Every deploy begins cold, by design — the alternative (an in-process wipe) was rejected above precisely because it cannot tell "cold on purpose" from "warm because a sibling already ran."
- **`load()` still runs on every miss.** A miss is the only way to discover the data was unchanged; there is no cheap staleness probe distinct from `load()` itself. This ADR does not close that gap — see [issue #549](https://github.com/paulomtts/pyjinhx/issues/549) for what it does and doesn't answer.
- **The render-cost threshold is a measurement, not a rule an author writes.** A class's verdict is decided once from its first render and never revisited, so it cannot flip between requests on machine load — but it also means the very first render of a class pays a cache write it may not have needed, and that write includes Jinja's one-time template compile, which biases the measurement toward "expensive" rather than toward wrongly skipping a real saving.

## Alternatives considered

- **A boot-epoch namespace, to let the operator skip getting the directory contract right.** A versioned key segment shared by every worker of a deployment, refreshed on restart, would have let the library guarantee volatility instead of documenting it as a contract. Designed, then discarded as overkill: it re-solves the exact "which restart is this" problem the ephemerality decision above already ruled out solving in-process, and it works *against* the actual requirement by letting a cache survive a same-release restart rather than dying with it. The requirement collapsed to one line — the store starts empty on every boot, so point it at a directory that already does that.
- **A process-level instance cache**, as 0009's original framing proposed (caching whole `ReactiveComponent` instances, keyed like the request-scoped registry). Rejected in favor of caching `load()` *results*: an instance holds slots, children, and session references that don't pickle cleanly, where a `load()` result is typically a plain Pydantic model. The registry itself stays request-scoped and untouched by this ADR.

## Related

- [Cache Backends](../api/cache-backends.md) — the full protocol, policy knobs, and operator-facing directory contract.
- [Migration: Cross-request `InvalidationBackend`](../migration.md#cross-request-invalidationbackend-deferred-at-10-landed-in-140) — what changed for an app upgrading from a 0.x Redis/SQLite invalidation backend.
- [Issue #549](https://github.com/paulomtts/pyjinhx/issues/549) — the discussion that scoped this, and what remains open after it.
