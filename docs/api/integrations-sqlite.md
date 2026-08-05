# SQLite cache backend

**There is no separate SQLite integration, because SQLite is already how the shipped one works.** `DiskCacheBackend` (`pyjinhx.integrations.diskcache`, installed with `pyjinhx[diskcache]`) stores its entries in SQLite — a `FanoutCache`, which spreads them over several databases so N workers writing do not queue behind one database-level write lock.

That also settles what an older version of this page called missing. Cross-process invalidation is not a second mechanism waiting to be built: every worker of a deployment opens the same directory, so an `evict()` in one is visible to the rest on their next read. It falls out of sharing a store rather than riding a channel beside it.

Two boundaries, both inherited from SQLite:

- **Local disk only.** Its locking is unreliable over NFS and other network filesystems, and a cache that corrupts under concurrency is worse than no cache. Documented rather than detected, because the check would be a guess about a mount point.
- **One machine, not one cluster.** A shared filesystem covers the workers inside a pod or container; four pods hold four independent caches. That is where a [Redis backend](integrations-redis.md) would earn its place.

See [Cache Backends](cache-backends.md) for the `CacheBackend` protocol, the per-class policy knobs, and the ephemeral-directory contract the disk backend expects.
