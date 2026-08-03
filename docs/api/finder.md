# Discovery & Assets

File discovery for `.pjx` templates and the registry-wide asset listing used by build tooling.

## walk_templates

```python
def walk_templates(template_dir: Path | str) -> Iterator[TemplateCandidate]
```

The `.pjx` files under `template_dir`, nested ones included, sorted by path. See [Template Discovery](parser.md#walk_templates) for the full description and `TemplateCandidate` fields.

## build_registry

```python
def build_registry(template_dir: Path | str, classes: Iterable[type]) -> None
```

Walk `template_dir` and publish a fresh tag → class registry. See [Template Discovery](parser.md#build_registry).

## get_class

```python
def get_class(tag_name: str) -> type | None
```

The component class registered for `tag_name`, or `None`. See [Template Discovery](parser.md#get_class).

## get_template_dir

```python
def get_template_dir() -> Path | None
```

The directory the last successful `build_registry` walked, or `None` if it hasn't run yet.

## all_assets

```python
def all_assets() -> tuple[tuple[Path, ...], tuple[Path, ...]]
```

Every CSS and JS path declared by any component class, registry-wide rather than session-scoped: a class contributes its assets whether or not it was rendered. Only classes imported by the time of the call are visible — import the component package before calling this from a build script.

**Returns:** The CSS paths then the JS paths, each deduped and in path-sorted order so repeated calls and repeated builds agree byte for byte.

```python
from pyjinhx.assets import all_assets

css_paths, js_paths = all_assets()
```

See also [Assets API](assets-api.md) for the per-request asset emission functions.
