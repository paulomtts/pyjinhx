# Redis invalidation integration

Reference `InvalidationBackend` for multi-worker setups. Configuring it also derives cross-request (per worker) caching of `load()` results.

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
from pyjinhx import PjxSettings, setup
from pyjinhx.integrations.redis import RedisInvalidationBackend

setup(
    app,
    settings=PjxSettings(
        invalidation_backend=RedisInvalidationBackend("redis://localhost:6379/0"),
    ),
    load_context_factory=...,
)
```

Or via environment (`PjxSettings.from_env()`):

```bash
REDIS_URL=redis://localhost:6379/0 uvicorn main:app
```

See [Configuration](config.md) and [Cache & Invalidation](cache-invalidation.md).
