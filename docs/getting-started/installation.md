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

## Dependencies

PyJinHx automatically installs these dependencies:

- **Jinja2** - Template engine
- **Pydantic** - Data validation and settings
- **MarkupSafe** - Safe HTML string handling

## Verify Installation

```python
from pyjinhx import BaseComponent, Renderer

print("PyJinHx installed successfully!")
```
