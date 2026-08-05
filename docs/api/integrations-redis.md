# Redis cache backend

**Not yet implemented.** There is no `pyjinhx.integrations.redis` module and no Redis backend class in pyjinhx. A future one would be an ordinary `CacheBackend` — the runtime-checkable protocol in `pyjinhx.reactive.backend`, four methods wide: `get`, `put`, `evict`, `clear`. Nothing above it would need a second mechanism: invalidation falls out of workers sharing one store, rather than riding a pub/sub channel beside it.

`DiskCacheBackend` (`pyjinhx.integrations.diskcache`, installed with `pyjinhx[diskcache]`) is the shipped implementation of that protocol, and it is also where the boundary falls — a shared filesystem is one machine, not one cluster, so four pods have four independent caches. That is where a Redis backend would earn its place. See [Cache Backends](cache-backends.md) for the protocol, the policy knobs and what the disk backend does today.
