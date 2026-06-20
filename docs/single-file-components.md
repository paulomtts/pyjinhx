# Single-file components

A `.pjx` file can hold its own Python class in a leading `{# python … #}` block:

```jinja
{# python
from pyjinhx import ReactiveComponent, MutationKey

class Keys(MutationKey):
    TODOS = "todos"

class Counter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=db.remaining())
#}
<div data-pjx-id="counter">{{ remaining }} left</div>
```

Import it like any module — no build step:

```python
from app.components.counter import Counter
Counter.load().render()
```

## Rules

- The block opens with `{# python` alone on the first line and closes at the
  first later line that is exactly `#}`.
- Exactly one component class per file. For a file with helper classes, set
  `__pjx_component__ = TheComponent` to name the one that is the component.
- A `.pjx` with no `{# python #}` block is a plain template/partial, not a
  component — importing it raises `ImportError`.
- A `.py` and a `.pjx` with the same stem on the same path is a hard error;
  remove one.

## Simple (non-reactive) example

For a component that has no reactivity dependency, use `BaseComponent`:

```jinja
{# python
from pyjinhx import BaseComponent

class Badge(BaseComponent):
    label: str
    count: int = 0
#}
<span class="badge">{{ label }} ({{ count }})</span>
```

```python
from app.components.badge import Badge

html = Badge(label="inbox", count=3).render()
```

## Editor type-checking

`.pjx` files are not standard Python, so a type checker cannot resolve
`from app.components.counter import Counter` without help. Generate
signature-only `.pyi` stubs:

```bash
python -m pyjinhx.stubgen .
```

Stubs land in a gitignored `.pjx/stubs/` cache that mirrors the import tree.
Point pyright at them once, in `pyproject.toml`:

```toml
[tool.pyright]
extraPaths = [".pjx/stubs"]
```

Run with `--check` in CI to catch stale stubs (exits 1 if any stub is out of date):

```bash
python -m pyjinhx.stubgen . --check
```

!!! note "The `.pjx/stubs/` directory is auto-gitignored"
    `stubgen` writes a `*` `.gitignore` inside `.pjx/` on first run, so the
    cache never appears in `git status`.
