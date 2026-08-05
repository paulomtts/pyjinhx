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

The `diskcache` extra pulls in the dependencies for `DiskCacheBackend`, which lets a `load()` result or a rendered shell be reused across requests instead of being rebuilt every time. Every worker on the machine shares one store, so a mutation in one is seen by the rest:

```bash
pip install "pyjinhx[diskcache]"
```

```bash
uv add "pyjinhx[diskcache]"
```

Optional in both directions: pyjinhx imports and runs without it, and installing it changes nothing until you pass a backend to `setup()`. See [Cache Backends](../api/cache-backends.md) for what it does and the directory it needs.

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
from pyjinhx import BaseComponent, render

print("PyJinHx installed successfully!")
```

## Upgrading from 0.4.x

Coming from an older render-only release? See [Migrating from 0.4.x](../migration.md) for the
compatibility matrix, the handful of mechanical fixes, and how to adopt the new reactive layer.
