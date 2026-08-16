"""Parse a template's leading ``{#def ... #}`` prop header into a prop spec.

A classless component template declares its props in a header that is the first
non-whitespace in the file::

    {#def title: str, count: int = 0, variant: str = "primary" #}

The header is a valid (inert) Jinja comment; pyjinhx reads it out-of-band. This
module only parses — turning the result into a component class is done by the
caller.
"""

import ast
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import create_model

if TYPE_CHECKING:
    from pyjinhx._component import _OpenComponent

_HEADER_RE = re.compile(r"\A\s*\{#\s*def\s+(?P<sig>.*?)\s*#\}", re.DOTALL)

_TYPES: dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "Any": Any,
}


def _resolve_annotation(node: ast.expr | None, field_name: str) -> Any:
    if node is None:
        return Any
    if isinstance(node, ast.Name):
        if node.id not in _TYPES:
            # The only emission point: None and the union wrappers are handled
            # by the branches below, so nesting never double-reports one prop.
            logger.warning(_UNRECOGNIZED_ANNOTATION_WARNING, field_name, node.id)
            return Any
        return _TYPES[node.id]
    if isinstance(node, ast.Constant) and node.value is None:
        return type(None)
    # T | None  ->  Optional[T]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _resolve_annotation(node.left, field_name)
        right = _resolve_annotation(node.right, field_name)
        if right is type(None):
            return left | None
        if left is type(None):
            return right | None
        return Any
    # Optional[T]
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Optional"
    ):
        return _resolve_annotation(node.slice, field_name) | None
    return Any


def parse_props_header(source: str) -> list[tuple[str, Any, Any]] | None:
    """Parse a ``{#def ... #}`` header; return ``[(name, type, default), ...]`` or None.

    ``default`` is ``Ellipsis`` (``...``) for a required prop. Raises ``ValueError``
    for a malformed signature, a non-literal default, or a duplicate prop.
    """
    # Imported here, not at module scope: Slot and Children are defined at the
    # bottom of _component.py, after _OpenComponent, whose class body reenters
    # this module — a top-level import would read them before they are bound.
    from pyjinhx._component import Children, Slot

    _TYPES["Slot"] = Slot
    _TYPES["Children"] = Children

    match = _HEADER_RE.match(source)
    if match is None:
        return None
    signature = match.group("sig")
    try:
        tree = ast.parse(f"def __pjx_props__({signature}): pass")
    except SyntaxError as exc:
        raise ValueError(
            f"invalid {{#def#}} header signature {signature!r}: {exc.msg}"
        ) from exc
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    arguments = func.args
    if (
        arguments.vararg
        or arguments.kwarg
        or arguments.kwonlyargs
        or arguments.posonlyargs
    ):
        raise ValueError(
            f"{{#def#}} header may only use simple named props: {signature!r}"
        )
    args = arguments.args
    defaults = arguments.defaults
    # Defaults bind to the *last* N params, so this offset maps index -> default.
    offset = len(args) - len(defaults)
    seen: set[str] = set()
    fields: list[tuple[str, Any, Any]] = []
    for index, arg in enumerate(args):
        name = arg.arg
        if name in seen:
            raise ValueError(f"{{#def#}} header has duplicate prop {name!r}")
        seen.add(name)
        annotation = _resolve_annotation(arg.annotation, name)
        if index >= offset:
            default_node = defaults[index - offset]
            try:
                default = ast.literal_eval(default_node)
            except (ValueError, SyntaxError) as exc:
                raise ValueError(
                    f"{{#def#}} header default for {name!r} must be a literal: "
                    f"{ast.unparse(default_node)!r}"
                ) from exc
        else:
            default = ...
        fields.append((name, annotation, default))
    return fields


def build_component_class(
    fields: list[tuple[str, Any, Any]], tag: str
) -> "type[_OpenComponent]":
    """Build an open-model component class named ``tag`` from parsed header fields.

    ``fields`` is ``parse_props_header``'s output verbatim: ``(name, annotation,
    default)``, with ``Ellipsis`` as the default for a required prop — which is
    already pydantic's own required sentinel, so each tuple maps straight onto a
    ``create_model`` field definition with no translation.

    The base is ``_OpenComponent`` rather than ``BaseComponent``: a header
    declares the props a template reads, not the full set of attributes a caller
    may pass through, so undeclared keys must land in ``model_extra`` instead of
    raising.
    """
    from pyjinhx._component import _OpenComponent

    definitions: dict[str, Any] = {
        name: (annotation, default) for name, annotation, default in fields
    }
    # create_model otherwise reads __module__ off the calling frame, which would
    # make a generated class's template and asset probing depend on which module
    # happened to call in. Pin it here; discovery repoints it at the template's
    # own package and calls rebuild_class_descriptor once the class is placed.
    cls = create_model(tag, __base__=_OpenComponent, __module__=__name__, **definitions)
    # Set after creation, not as a create_model field: a leading underscore is a
    # pydantic private attribute, and this is a plain class-level marker that
    # downstream code reads off the type, never off an instance.
    cls._pjx_classless = True  # pyright: ignore[reportAttributeAccessIssue]
    return cls


logger = logging.getLogger("pyjinhx")


def template_has_props_header(template_path: Path) -> bool:
    """Whether the template at ``template_path`` opens with a ``{#def#}`` header.

    Answers False for anything it cannot read or parse. This runs at class
    registration, where the template path is a candidate that nothing has
    proven exists yet, and a diagnostic must never be the thing that breaks an
    import — the caller that actually loads the template still raises its own
    error if the file is missing.
    """
    try:
        source = template_path.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        return parse_props_header(source) is not None
    except ValueError:
        # A malformed header is still a header, but header-parse correctness
        # belongs to the classless path; staying silent here keeps a broken
        # header from producing two unrelated complaints.
        return False


_STALE_DEF_HEADER_WARNING = (
    "<%s>: a {#def#} header is present but a Python class is registered — "
    "the header is ignored. Remove the header (or the class)."
)

_UNRECOGNIZED_ANNOTATION_WARNING = (
    "<%s>: {#def#} annotation %r is not a recognized type — the prop falls back "
    "to Any. A header cannot import names; use a builtin type or drop the "
    "annotation."
)


def warn_stale_def_header(cls: type) -> None:
    """Report ``cls``'s ignored ``{#def#}`` header, at most once per class.

    The "already reported" bit lives on the class rather than in a module-level
    set: the fact is per-class, so the class is where it belongs, and the render
    path gains no shared mutable state.
    """
    if getattr(cls, "_pjx_stale_header_warned", False):
        return
    cls._pjx_stale_header_warned = True  # pyright: ignore[reportAttributeAccessIssue]
    logger.warning(_STALE_DEF_HEADER_WARNING, cls.__name__)
