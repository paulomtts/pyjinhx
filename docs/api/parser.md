# Template Discovery

Public API for finding `.pjx` component templates on disk and resolving PascalCase tags to component classes.

See [PascalCase Tags](../guide/tags.md) for usage patterns.

## walk_templates

```python
def walk_templates(template_dir: Path | str) -> Iterator[TemplateCandidate]
```

Walk `template_dir` for `.pjx` files, nested directories included, yielding them sorted by path. Pure over the filesystem: nothing is registered, cached, or deduplicated — the same tree always yields the same sequence.

### Usage

```python
from pyjinhx.discovery import walk_templates

for candidate in walk_templates("templates"):
    print(candidate.tag_name, candidate.path)
```

**Raises:** `NotADirectoryError` if `template_dir` is not a directory.

## TemplateCandidate

```python
class TemplateCandidate(NamedTuple):
    tag_name: str
    path: Path
```

One `.pjx` file the walk found, and the tag name it would answer to.

| Field | Description |
|-------|-------------|
| `tag_name` | The snake_case name derived from the file's stem |
| `path` | The file's path |

## get_class

```python
def get_class(tag_name: str) -> type | None
```

Return the component class registered for `tag_name`, or `None` when nothing claims that tag. Never raises on a miss — an unknown tag is treated as ordinary markup and passed through verbatim during rendering.

```python
# <PJXCard class_name="note">Hello</PJXCard>
from pyjinhx.discovery import get_class

cls = get_class("pjx_card")
```

## register_class

```python
def register_class(tag_name: str, cls: type) -> None
```

Publish `cls` under `tag_name` unless the tag already has an owner. The one way a tag is claimed after the import-time build — used by `component()` to register a classless wrapper on demand. A tag that is already owned is left alone: a class registered this way never shadows a declared one; the loser is logged, not silently dropped.

## get_template_dir

```python
def get_template_dir() -> Path | None
```

The directory the last successful `build_registry` walked, or `None` if it hasn't run yet.

## build_registry

```python
def build_registry(template_dir: Path | str | None, classes: Iterable[type]) -> None
```

Walk `template_dir` and publish a fresh tag → class registry, assembled complete before it is published so a reader never sees a half-built map. Called once at startup; a class with `pjx_replace=True` wins any tag collision, otherwise the collision is logged and resolved deterministically.
