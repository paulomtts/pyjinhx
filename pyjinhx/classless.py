"""The classless factory: a component class for a template nobody declared.

Discovery deliberately leaves an orphan `.pjx` file unregistered — a template
with no class is a normal thing to find on disk, not an error. `component()` is
the other half of that decision: the on-demand path that says "give me a class
for this template anyway", building one from the template's `{#def#}` header
when it has one and a permissive placeholder when it does not.
`component_for_tag()` is the renderer's half: on a tag miss it builds a class
only for an orphan template that carries a header.

Sits above _component.py, discovery.py and props_header.py and only calls into
them: parsing stays in props_header, the tag -> class mapping stays discovery's
to write, and nothing here re-implements either.
"""

import sys
import threading
import types
from pathlib import Path
from typing import Any

from pyjinhx import discovery
from pyjinhx._component import (
    BaseComponent,
    _OpenComponent,
    _pascal_to_snake,
    rebuild_class_descriptor,
)
from pyjinhx.props_header import build_component_class, parse_props_header
from pyjinhx.segments import RE_PASCAL_CASE_TAG_NAME

_synthetic_modules: dict[Path, str] = {}
_synthetic_modules_lock = threading.Lock()
_build_lock = threading.Lock()


def _find_template(tag: str, template_dir: Path | str | None) -> Path:
    """The `.pjx` file named ``tag`` under ``template_dir``.

    Uses discovery's own walk rather than a second resolution rule, so a
    template the factory can build from is exactly a template discovery could
    have registered. The first match in the walk's sorted order wins — the walk
    reports duplicates rather than deciding between them, and this needs one
    file, not an arbitration.
    """
    root = template_dir if template_dir is not None else discovery.get_template_dir()
    if root is None:
        raise LookupError(
            f"component({tag!r}) has no directory to search: pass template_dir, "
            f"or call discovery.build_registry first so the template directory "
            f"is known."
        )
    for candidate in discovery.walk_templates(root):
        if candidate.tag_name == tag:
            return candidate.path
    raise LookupError(
        f"component() found no template for tag {tag!r}: no file named "
        f"{tag}.pjx exists under {str(Path(root))!r}."
    )


def _module_for_directory(directory: Path) -> str:
    """The name of a module whose file sits in ``directory``, creating it once.

    Template and asset resolution probe the directory of the module that
    defined a class, and a generated class was defined by no file at all. A
    synthetic module placed in the template's own directory gives the existing
    walk a real answer, instead of teaching it a second rule for classes that
    came from disk. One module per directory, cached, so every class built from
    the same directory shares it.
    """
    key = directory.resolve()
    with _synthetic_modules_lock:
        name = _synthetic_modules.get(key)
        if name is None:
            name = f"pyjinhx._classless_{len(_synthetic_modules)}"
            module = types.ModuleType(name)
            module.__file__ = str(key / "__init__.py")
            sys.modules[name] = module
            _synthetic_modules[key] = name
    return name


def _placeholder_class(name: str, tag: str) -> type[_OpenComponent]:
    """A prop-less open class for a template that declares no props.

    A template with no header still renders — it just reads whatever the caller
    passed. Nothing is declared, so every attribute arrives as an extra, which
    is exactly what the open base already does.
    """
    cls = types.new_class(name, (_OpenComponent,))
    # Set after creation, not in the class body: pydantic turns a leading
    # underscore assignment in the body into a private instance attribute, and
    # these are plain class-level markers read off the type.
    cls._pjx_classless = True  # pyright: ignore[reportAttributeAccessIssue]
    cls._pjx_template = tag  # pyright: ignore[reportAttributeAccessIssue]
    return cls


def component(name: str, template_dir: Path | str | None = None) -> type[BaseComponent]:
    """The component class for ``name``, building one from its template if needed.

    Returns the class already registered for the tag when there is one, so
    calling this twice — or calling it for a hand-declared component — hands
    back the same object and never shadows a declared class.
    """
    if RE_PASCAL_CASE_TAG_NAME.fullmatch(name) is None:
        raise ValueError(
            f"component() needs a PascalCase component name; {name!r} is not "
            f"one, so no template name could be derived from it."
        )
    tag = _pascal_to_snake(name)
    registered = discovery.get_class(tag)
    if registered is not None:
        return registered  # pyright: ignore[reportReturnType]
    template_path = _find_template(tag, template_dir)
    return _register_first(
        tag, _build(name, tag, template_path, _read_header(template_path))
    )


def component_for_tag(name: str) -> type[BaseComponent] | None:
    """The class a ``<name>`` tag renders as when no class claims it, or ``None``.

    The renderer's fallback on a tag miss. Only an orphan template discovery
    recorded for the tag is considered, so a tag with no file — a web
    component, a typo — costs one dict lookup and no filesystem access. That
    template is read once: a ``{#def#}`` header (an empty one counts) makes it
    a component, built and registered as `component()` would; no header means
    it is plain markup, and that answer is remembered.

    Raises ``LookupError`` when several orphan templates share the tag and any
    of them has a header, since nothing says which one the tag means.
    """
    tag = _pascal_to_snake(name)
    registered = discovery.get_class(tag)
    if registered is not None:
        return registered  # pyright: ignore[reportReturnType]
    if not discovery.get_orphan_templates(tag):
        return None
    paths = discovery.get_orphan_templates(tag)
    headers = [_read_header(path) for path in paths]
    if all(fields is None for fields in headers):
        discovery.forget_orphan(tag)
        return None
    if len(headers) > 1:
        raise LookupError(
            f"<{name}> could be any of {len(paths)} templates: "
            f"{', '.join(str(path) for path in paths)}. Rename all but one, "
            f"or call component({name!r}) to pick the first."
        )
    return _register_first(tag, _build(name, tag, paths[0], headers[0]))


def _read_header(template_path: Path) -> list[tuple[str, Any, Any]] | None:
    """The parsed ``{#def#}`` header of ``template_path``, or ``None`` without one."""
    source = template_path.read_text(encoding="utf-8")
    try:
        return parse_props_header(source, str(template_path))
    except ValueError as exc:
        raise ValueError(f"{template_path}: {exc}") from exc


def _build(
    name: str, tag: str, template_path: Path, fields: list[tuple[str, Any, Any]] | None
) -> type[BaseComponent]:
    """The class for ``template_path``, placed beside it but not yet registered."""
    if fields is None:
        cls = _placeholder_class(name, tag)
    else:
        cls = build_component_class(fields, name, template_path)
    cls.__module__ = _module_for_directory(template_path.parent)
    # The class was built with a provisional descriptor pointing at
    # whichever module generated it; only now does it sit beside its own
    # template.
    rebuild_class_descriptor(cls)
    return cls


def _register_first(tag: str, cls: type[BaseComponent]) -> type[BaseComponent]:
    """Publish ``cls`` under ``tag`` unless a racing build got there first.

    Building stays outside the lock: resolving a header's dotted names imports
    modules, and one that calls `component()` while importing would otherwise
    wait on this same lock forever.
    """
    with _build_lock:
        registered = discovery.get_class(tag)
        if registered is not None:
            return registered  # pyright: ignore[reportReturnType]
        discovery.register_class(tag, cls)
        return cls
