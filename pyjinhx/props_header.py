"""Parse a template's leading ``{#def ... #}`` prop header into a prop spec.

A classless component template declares its props in a header that is the first
non-whitespace in the file::

    {#def title: str, count: int = 0, variant: str = "primary" #}

The header is a valid (inert) Jinja comment; pyjinhx reads it out-of-band.

A dotted name is an absolute import path, resolved with ``pkgutil.resolve_name``.
The header itself is never compiled or ``eval``'d, but a template is trusted
code: resolving a name imports its module, running that module's top level,
and a ``pkg.f()`` default calls ``f`` for every instance::

    {#def when: datetime.datetime, size: int = app.ui.PAGE_SIZE,
          at: datetime.datetime = datetime.datetime.now() #}

as a type, as a constant default, and with empty parentheses as a default
factory called per instance. A bare name is never imported (a typo must not
become an import), and a leading dot is not Python syntax, so there are no
relative paths. Parsing imports nothing; the names resolve when the class is
built, once per class, and the modules they import stay in ``sys.modules`` like
any other import, so a template reload never re-imports them.
"""

import ast
import logging
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from jinja2 import TemplateSyntaxError
from pydantic import Field, create_model

from pyjinhx.sfc import LEGACY_HEADER_RE
from pyjinhx.template_blocks import find_block

if TYPE_CHECKING:
    from pyjinhx._component import _OpenComponent

_TYPES: dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "Any": Any,
}


@dataclass(frozen=True)
class _DottedType:
    """An annotation that names an import path somewhere inside it.

    Kept unresolved until the class is built: parsing also runs at class
    registration, while the app's own modules may still be importing.
    """

    node: ast.expr
    field_name: str


def _dotted_name(node: ast.expr) -> str | None:
    """``node`` as ``a.b.c`` text if it is a pure chain of two or more names."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not parts or not isinstance(node, ast.Name):
        return None
    return ".".join([node.id, *reversed(parts)])


@dataclass(frozen=True)
class _DottedDefault:
    """A default that names an import path, read once when the class is built.

    ``call`` marks the ``path()`` form: the name is a factory, called per instance.
    """

    path: str
    field_name: str
    call: bool


def _names_an_import_path(node: ast.expr) -> bool:
    return any(isinstance(child, ast.Attribute) for child in ast.walk(node))


def _import(path: str, field_name: str, owner: str) -> Any:
    try:
        return pkgutil.resolve_name(path)
    except (ImportError, AttributeError) as exc:
        raise ValueError(
            f"{owner}: {{#def#}} prop {field_name!r} names {path!r}, which does "
            f"not import: {exc}"
        ) from exc


def _resolve_annotation(
    node: ast.expr | None, field_name: str, owner: str = "{#def#} header"
) -> Any:
    if node is None:
        return Any
    if isinstance(node, ast.Attribute):
        path = _dotted_name(node)
        return Any if path is None else _import(path, field_name, owner)
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
        left = _resolve_annotation(node.left, field_name, owner)
        right = _resolve_annotation(node.right, field_name, owner)
        if right is type(None):
            return left | None
        if left is type(None):
            return right | None
        return left | right
    # Optional[T]
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Optional"
    ):
        return _resolve_annotation(node.slice, field_name, owner) | None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        if node.value.id == "Literal":
            return _resolve_literal(node.slice, field_name)
        if node.value.id in ("list", "dict", "tuple"):
            elements = (
                node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            )
            arguments = tuple(
                # The `...` of `tuple[int, ...]` is itself the argument.
                ...
                if isinstance(e, ast.Constant) and e.value is Ellipsis
                else _resolve_annotation(e, field_name, owner)
                for e in elements
            )
            return _TYPES[node.value.id][arguments]
    return Any


def _resolve_literal(node: ast.expr, field_name: str) -> Any:
    members = node.elts if isinstance(node, ast.Tuple) else [node]
    try:
        values = tuple(ast.literal_eval(member) for member in members)
    except ValueError as exc:
        raise ValueError(
            f"{{#def#}} Literal members for {field_name!r} must be literals"
        ) from exc
    return Literal[values]


def _parse_default(node: ast.expr, field_name: str) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        pass
    if isinstance(node, ast.Call):
        path = None if node.args or node.keywords else _dotted_name(node.func)
    else:
        path = _dotted_name(node)
    if path is None:
        raise ValueError(
            f"{{#def#}} header default for {field_name!r} must be a literal, a "
            "dotted name (pkg.mod.NAME) or a dotted name called with no arguments "
            f"(pkg.mod.make()): {ast.unparse(node)!r}"
        )
    return _DottedDefault(path, field_name, call=isinstance(node, ast.Call))


def parse_props_header(
    source: str, filename: str = "<template>"
) -> list[tuple[str, Any, Any]] | None:
    """Parse a ``{#def ... #}`` header; return ``[(name, type, default), ...]`` or None.

    The header is found anywhere in ``source``. ``default`` is ``Ellipsis``
    (``...``) for a required prop. A type or default that names an import path
    comes back unresolved, for ``build_component_class`` to import. Raises
    ``ValueError`` for a malformed signature, a default that is neither a
    literal nor a dotted name, or a duplicate prop, and ``TemplateSyntaxError``
    when ``source`` holds two headers.
    """
    # Imported here, not at module scope: Slot and Children are defined at the
    # bottom of _component.py, after _OpenComponent, whose class body reenters
    # this module — a top-level import would read them before they are bound.
    from pyjinhx._component import AttrValue, Children, ExtraAttrs, Slot

    _TYPES["Slot"] = Slot
    _TYPES["Children"] = Children
    _TYPES["ExtraAttrs"] = ExtraAttrs
    _TYPES["AttrValue"] = AttrValue

    block = find_block(source, "def", filename)
    if block is not None:
        signature = block.body
    else:
        match = LEGACY_HEADER_RE.match(source)
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
        if arg.annotation is not None and _names_an_import_path(arg.annotation):
            annotation = _DottedType(arg.annotation, name)
        else:
            annotation = _resolve_annotation(arg.annotation, name)
        if index >= offset:
            default = _parse_default(defaults[index - offset], name)
        else:
            default = ...
        fields.append((name, annotation, default))
    return fields


def build_component_class(
    fields: list[tuple[str, Any, Any]], tag: str, template_path: Path | None = None
) -> "type[_OpenComponent]":
    """Build an open-model component class named ``tag`` from parsed header fields.

    ``fields`` is ``parse_props_header``'s output verbatim: ``(name, annotation,
    default)``, with ``Ellipsis`` as the default for a required prop — which is
    already pydantic's own required sentinel, so each tuple maps onto a
    ``create_model`` field definition once its dotted names are imported. An
    import that fails raises ``ValueError`` naming the tag, ``template_path``
    when given, the prop and the path.

    The base is ``_OpenComponent`` rather than ``BaseComponent``: a header
    declares the props a template reads, not the full set of attributes a caller
    may pass through, so undeclared keys must land in ``model_extra`` instead of
    raising.
    """
    from pyjinhx._component import _OpenComponent

    owner = f"<{tag}>" if template_path is None else f"<{tag}> ({template_path})"
    definitions: dict[str, Any] = {
        name: (_resolve_dotted(annotation, owner), _resolve_dotted(default, owner))
        for name, annotation, default in fields
    }
    # create_model otherwise reads __module__ off the calling frame, which would
    # make a generated class's template and asset probing depend on which module
    # happened to call in. Pin it here; discovery repoints it at the template's
    # own package and calls rebuild_class_descriptor once the class is placed.
    # The base class already owns the id field; declaring it required only
    # switches off auto-generation.
    id_definition = definitions.pop("id", None)
    if id_definition is not None and id_definition != (str, ...):
        raise ValueError(
            f"<{tag}>: in a {{#def#}} header id may only be declared as a "
            "required str (`id: str`)"
        )
    cls = create_model(tag, __base__=_OpenComponent, __module__=__name__, **definitions)
    if id_definition is not None:
        cls.auto_id = False
    # Set after creation, not as a create_model field: a leading underscore is a
    # pydantic private attribute, and this is a plain class-level marker that
    # downstream code reads off the type, never off an instance.
    cls._pjx_classless = True  # pyright: ignore[reportAttributeAccessIssue]
    return cls


def _resolve_dotted(value: Any, owner: str) -> Any:
    if isinstance(value, _DottedType):
        return _resolve_annotation(value.node, value.field_name, owner)
    if isinstance(value, _DottedDefault):
        target = _import(value.path, value.field_name, owner)
        if not value.call:
            return target
        if not callable(target):
            # ValueError like every other header mistake, so callers catch one type.
            raise ValueError(  # noqa: TRY004
                f"{owner}: {{#def#}} default for {value.field_name!r} calls "
                f"{value.path!r}, which is not callable"
            )
        return Field(default_factory=target)
    return value


logger = logging.getLogger("pyjinhx")


def template_has_props_header(source: str) -> bool:
    """Whether the template ``source`` carries a ``{#def#}`` header.

    Answers False for anything it cannot parse. This runs at class
    registration, and a diagnostic must never be the thing that breaks an
    import.
    """
    try:
        return parse_props_header(source) is not None
    except (ValueError, TemplateSyntaxError):
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
    "to Any. Use a builtin type, a dotted import path (pkg.mod.Type) or drop "
    "the annotation."
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
