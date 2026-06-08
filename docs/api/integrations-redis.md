# Redis invalidation integration

Reference `InvalidationBackend` for multi-worker `CacheScope.PROCESS` setups.

Not exported from top-level `pyjinhx` — import from the integrations submodule:

```python
from pyjinhx.integrations.redis import RedisInvalidationBackend
```

Install optional dependencies:

```bash
pip install pyjinhx[redis]
```

## RedisInvalidationBackend

```python
class RedisInvalidationBackend(InvalidationBackend):
    def __init__(self, redis_url: str, *, channel: str = "pyjinhx:invalidate") -> None: ...
```

Publishes dirtied keys over Redis pub/sub so every worker evicts its local `load()` cache.

| URL | Use |
|-----|-----|
| `redis://localhost:6379/0` | Real Redis |
| `memory://` | In-process FakeRedis (tests, single-process demos) |

## With setup

```python
from pyjinhx import CacheScope, PyJinhxSettings, setup
from pyjinhx.integrations.redis import RedisInvalidationBackend

setup(
    app,
    settings=PyJinhxSettings(
        cache_scope=CacheScope.PROCESS,
        invalidation_backend=RedisInvalidationBackend("redis://localhost:6379/0"),
    ),
    load_context_factory=...,
)
```

Or via environment (`PyJinhxSettings.from_env()`):

```bash
PJX_LOAD_CACHE_SCOPE=process REDIS_URL=redis://localhost:6379/0 uvicorn main:app
```

See [Configuration](config.md) and [Cache & Invalidation](cache-invalidation.md).
