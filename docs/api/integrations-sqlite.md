# SQLite invalidation integration

Reference `InvalidationBackend` for single-host multi-worker setups. Fans out `load()`-cache invalidation across worker processes using a shared SQLite file — no external service required. Configuring it also derives cross-request (per-worker) caching of `load()` results.

Not exported from top-level `pyjinhx` — import from the integrations submodule:

```python
from pyjinhx.integrations.sqlite import SqliteInvalidationBackend
```

No optional dependencies needed — `sqlite3` is part of the Python standard library.

## SqliteInvalidationBackend

```python
class SqliteInvalidationBackend(InvalidationBackend):
    def __init__(
        self,
        db_path: str,
        *,
        channel: str = "pyjinhx:invalidate",
        poll_interval: float = 0.5,
        retention: float = 5.0,
    ) -> None: ...
```

Writes dirtied keys to a shared SQLite event log so every worker on the same host evicts its local `load()` cache. Uses WAL mode and a background polling thread; no broker or network hop required.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `db_path` | *(required)* | Filesystem path to the SQLite database file. Must be a real file path — see caveats. |
| `channel` | `"pyjinhx:invalidate"` | Namespaces apps that share one database file. |
| `poll_interval` | `0.5` | Seconds between poll cycles. Invalidation latency is approximately this value. |
| `retention` | `5.0` | Seconds of event history kept before pruning. Workers stalled longer than this may miss invalidations. |

## With setup

```python
from pyjinhx import PjxSettings, setup
from pyjinhx.integrations.sqlite import SqliteInvalidationBackend

setup(
    app,
    settings=PjxSettings(
        invalidation_backend=SqliteInvalidationBackend("/var/lib/myapp/pjx.db"),
    ),
    load_context_factory=...,
)
```

Or via environment (`PjxSettings.from_env()`):

```bash
export PJX_INVALIDATION_DB=/var/lib/myapp/pjx.db
```

If both `REDIS_URL` and `PJX_INVALIDATION_DB` are set, Redis wins.

## Caveats

**Single-host only.** SQLite file locking is unreliable over network filesystems (NFS, CIFS, etc.). Use the Redis backend for multi-host deployments.

**`:memory:` is unsupported.** Each process receives a private in-memory database, so there is no cross-process fan-out. Always pass a real file path.

**WAL sidecar files.** SQLite WAL mode leaves `-wal` and `-shm` files next to the database. This is expected and normal.

**Bounded staleness on long stalls.** A worker paused longer than `retention` seconds may miss pruned invalidation events, resulting in a bounded period of stale cached data. This is an accepted trade-off of the polling design.

See [Configuration](config.md) and [Cache & Invalidation](cache-invalidation.md).
