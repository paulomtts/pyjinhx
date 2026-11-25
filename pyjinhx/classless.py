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
from pyjinhx.importer import import_document, loaded_document, opener_line
from pyjinhx.props_header import build_component_class, parse_props_header
from pyjinhx.segments import RE_PASCAL_CASE_TAG_NAME
from pyjinhx.sfc import BlockSyntaxError, python_block

_synthetic_modules: dict[Path, str] = {}
_synthetic_modules_lock = threading.Lock()
_build_lock = threading.Lock()
# Tags found ambiguous, with the orphan tuple they were found in. Discovery
# builds new tuples on every walk, so the identity check retires an entry
# once the registry is rebuilt. Guarded by _build_lock.
_ambiguous: dict[str, tuple[tuple[Path, ...], str]] = {}


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
    source = template_path.read_text(encoding="utf-8-sig")
    documented = register_document(template_path, source)
    if documented is not None:
        return documented
    fields = _parse_header(template_path, source)
    return _register_first(tag, _build(name, tag, template_path, fields))


def component_for_tag(name: str) -> type[BaseComponent] | None:
    """The class a ``<name>`` tag renders as when no class claims it, or ``None``.

    The renderer's fallback on a tag miss. Only an orphan template discovery
    recorded for the tag is considered, so a tag with no file — a web
    component, a typo — costs one dict lookup and no filesystem access. Each
    template is read once: a ``{#def#}`` header (an empty one counts) makes it
    a component, built and registered as `component()` would; no header means
    it is plain markup, and that answer is remembered. A file deleted since
    discovery counts as having no header.

    Raises ``LookupError`` when several orphan templates share the tag and
    more than one has a header, since nothing says which one the tag means.
    """
    tag = _pascal_to_snake(name)
    registered = discovery.get_class(tag)
    if registered is not None:
        return registered  # pyright: ignore[reportReturnType]
    paths = discovery.get_orphan_templates(tag)
    if not paths:
        return None
    with _build_lock:
        remembered = _ambiguous.get(tag)
    if remembered is not None and remembered[0] is paths:
        raise LookupError(remembered[1])
    headers = []
    for path in paths:
        documented, fields = _inspect_orphan(path)
        if documented is not None:
            return documented
        headers.append((path, fields))
    headed = [(path, fields) for path, fields in headers if fields is not None]
    if not headed:
        discovery.forget_orphan(tag)
        return None
    if len(headed) > 1:
        message = (
            f"<{name}> could be any of {len(headed)} templates: "
            f"{', '.join(str(path) for path, _ in headed)}. Rename all but one, "
            f"or call component({name!r}) to pick the first."
        )
        with _build_lock:
            _ambiguous[tag] = (paths, message)
        raise LookupError(message)
    path, fields = headed[0]
    return _register_first(tag, _build(name, tag, path, fields))


def _inspect_orphan(
    path: Path,
) -> tuple[type | None, list[tuple[str, Any, Any]] | None]:
    """The document class of an orphan template, or else its header fields.

    A file deleted since discovery has neither. The file is read once.
    """
    source = _orphan_source(path)
    if source is None:
        return None, None
    documented = register_document(path, source)
    if documented is not None:
        return documented, None
    return None, _parse_header(path, source)


def register_document(
    path: Path, source: str | None = None
) -> type[BaseComponent] | None:
    """The class of the ``.pjx`` document at ``path``, imported and registered.

    ``None`` when the file holds no ``{#python`` block. ``source`` is the file's
    text when the caller has read it already. A document the app
    already imported is not imported again, and a tag that already has an owner
    keeps it. The import runs outside the registry lock, like a header's.

    Raises:
        BlockSyntaxError: The file opens a block it does not close properly.
        ImportError: The document cannot be imported, or is shadowed.
    """
    loaded = loaded_document(path)
    if loaded is None:
        text = path.read_text(encoding="utf-8-sig") if source is None else source
        line = opener_line(text)
        if line is None:
            return None
        _check_block(text, path, line)
        import_document(path)
        loaded = loaded_document(path)
        if loaded is None:
            raise ImportError(
                f"{path} was imported but is not loaded as a document: another "
                f"loader made its module, or its block is still running.",
                path=str(path),
            )
    tag = _pascal_to_snake(loaded[1].__name__)
    registered = _register_first(tag, loaded[1])  # pyright: ignore[reportArgumentType]
    discovery.forget_orphan(tag)
    return registered


def _check_block(text: str, path: Path, line: int) -> None:
    """Refuse a malformed block in a file that opens one at ``line``, saying why
    the file counts as a document at all."""
    try:
        python_block(text, str(path))
    except BlockSyntaxError as error:
        raise BlockSyntaxError(
            error.code,
            f"{error.msg}; this file is imported as a document because line "
            f"{line} opens a {{#python block",
            (str(path), error.lineno or 1, error.offset or 1, error.text or ""),
        ) from error


def _orphan_source(template_path: Path) -> str | None:
    """The text of ``template_path``, or ``None`` for a file deleted since discovery."""
    try:
        return template_path.read_text(encoding="utf-8-sig")
    except OSError:
        return None


def _parse_header(
    template_path: Path, source: str
) -> list[tuple[str, Any, Any]] | None:
    """The parsed ``{#def#}`` header of ``source``, or ``None`` without one."""
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
