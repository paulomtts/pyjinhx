# SQLite invalidation integration

**Not yet implemented.** There is currently no `pyjinhx.integrations.sqlite` module and no `SqliteInvalidationBackend` class in pyjinhx.

Cross-process invalidation fan-out today lives entirely in-process, in `pyjinhx.reactive.fanout`: each worker walks its own request's `X-PJX-Mounted` manifest against that request's dirtied keys and re-renders the regions that need it. There is no shared-database or other mechanism yet for fanning a mutation's dirtied keys out to other worker processes on the same host.

See [Cache & Invalidation](cache-invalidation.md) for the fan-out mechanism that does exist today.
