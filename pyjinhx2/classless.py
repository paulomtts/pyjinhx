"""The classless factory: a component class for a template nobody declared.

Discovery deliberately leaves an orphan `.pjx` file unregistered — a template
with no class is a normal thing to find on disk, not an error. `component()` is
the other half of that decision: the on-demand path that says "give me a class
for this template anyway", building one from the template's `{#def#}` header
when it has one and a permissive placeholder when it does not.

Sits above component.py, discovery.py and props_header.py and only calls into
them: parsing stays in props_header, the tag -> class mapping stays discovery's
to write, and nothing here re-implements either.
"""

import sys
import types
from pathlib import Path

from pyjinhx2 import discovery
from pyjinhx2.component import (
    OpenComponent,
    _pascal_to_snake,
    rebuild_class_descriptor,
)
from pyjinhx2.props_header import build_component_class, parse_props_header
from pyjinhx2.segments import RE_PASCAL_CASE_TAG_NAME

_synthetic_modules: dict[Path, str] = {}


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
    name = _synthetic_modules.get(key)
    if name is None:
        name = f"pyjinhx2._classless_{len(_synthetic_modules)}"
        module = types.ModuleType(name)
        module.__file__ = str(key / "__init__.py")
        sys.modules[name] = module
        _synthetic_modules[key] = name
    return name


def _placeholder_class(name: str, tag: str) -> type[OpenComponent]:
    """A prop-less open class for a template that declares no props.

    A template with no header still renders — it just reads whatever the caller
    passed. Nothing is declared, so every attribute arrives as an extra, which
    is exactly what the open base already does.
    """
    cls = types.new_class(name, (OpenComponent,))
    # Set after creation, not in the class body: pydantic turns a leading
    # underscore assignment in the body into a private instance attribute, and
    # these are plain class-level markers read off the type.
    cls._pjx_classless = True  # pyright: ignore[reportAttributeAccessIssue]
    cls._pjx_template = tag  # pyright: ignore[reportAttributeAccessIssue]
    return cls


def component(name: str, template_dir: Path | str | None = None) -> type[OpenComponent]:
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
    fields = parse_props_header(template_path.read_text(encoding="utf-8"))
    if fields is None:
        cls = _placeholder_class(name, tag)
    else:
        cls = build_component_class(fields, name)
    cls.__module__ = _module_for_directory(template_path.parent)
    # The class was built with a provisional descriptor pointing at whichever
    # module generated it; only now does it sit beside its own template.
    rebuild_class_descriptor(cls)
    discovery.register_class(tag, cls)
    return cls
