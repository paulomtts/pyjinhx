# Installation

## Requirements

- Python 3.13 or higher

## Install with pip

```bash
pip install pyjinhx
```

## Install with uv

```bash
uv add pyjinhx
```

## Optional extras

The `redis` extra pulls in the dependencies for the Redis invalidation backend (used across multiple workers; configuring it also enables cross-request caching):

```bash
pip install pyjinhx[redis]
```

## Dependencies

PyJinHx automatically installs these runtime dependencies:

- **Jinja2** - Template engine
- **MarkupSafe** - Safe HTML string handling
- **Pydantic** - Data validation and settings

PyJinHx does **not** install a web framework. FastAPI, Starlette, and uvicorn are user-supplied — install them yourself before following the [FastAPI quickstart](../integrations/fastapi.md) or [Build an App](build-an-app.md):

```bash
pip install fastapi uvicorn
```

## Verify Installation

```python
from pyjinhx import BaseComponent, Renderer

print("PyJinHx installed successfully!")
```

## Upgrading from 0.4.x

Coming from an older render-only release? See [Migrating from 0.4.x](../migration.md) for the
compatibility matrix, the handful of mechanical fixes, and how to adopt the new reactive layer.
