# Redis invalidation integration

**Not yet implemented.** There is currently no `pyjinhx.integrations.redis` module and no `RedisInvalidationBackend` class in pyjinhx.

Cross-process invalidation fan-out today lives entirely in-process, in `pyjinhx.reactive.fanout`: each worker walks its own request's `X-PJX-Mounted` manifest against that request's dirtied keys and re-renders the regions that need it. There is no mechanism yet for propagating a mutation's dirtied keys to *other* worker processes or hosts, Redis-backed or otherwise.

See [Cache & Invalidation](cache-invalidation.md) for the fan-out mechanism that does exist today.
