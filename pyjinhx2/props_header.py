"""Parse a template's leading ``{#def ... #}`` prop header into a prop spec.

A classless component template declares its props in a header that is the first
non-whitespace in the file::

    {#def title: str, count: int = 0, variant: str = "primary" #}

The header is a valid (inert) Jinja comment; pyjinhx reads it out-of-band. This
module only parses — turning the result into a component class is done by the
caller.
"""

import ast
import re
from typing import Any

from pydantic import create_model

from pyjinhx2.component import OpenComponent

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


def _resolve_annotation(node: ast.expr | None) -> Any:
    if node is None:
        return Any
    if isinstance(node, ast.Name):
        return _TYPES.get(node.id, Any)
    if isinstance(node, ast.Constant) and node.value is None:
        return type(None)
    # T | None  ->  Optional[T]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _resolve_annotation(node.left)
        right = _resolve_annotation(node.right)
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
        return _resolve_annotation(node.slice) | None
    return Any


def parse_props_header(source: str) -> list[tuple[str, Any, Any]] | None:
    """Parse a ``{#def ... #}`` header; return ``[(name, type, default), ...]`` or None.

    ``default`` is ``Ellipsis`` (``...``) for a required prop. Raises ``ValueError``
    for a malformed signature, a non-literal default, or a duplicate prop.
    """
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
        annotation = _resolve_annotation(arg.annotation)
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
) -> type[OpenComponent]:
    """Build an open-model component class named ``tag`` from parsed header fields.

    ``fields`` is ``parse_props_header``'s output verbatim: ``(name, annotation,
    default)``, with ``Ellipsis`` as the default for a required prop — which is
    already pydantic's own required sentinel, so each tuple maps straight onto a
    ``create_model`` field definition with no translation.

    The base is ``OpenComponent`` rather than ``BaseComponent``: a header
    declares the props a template reads, not the full set of attributes a caller
    may pass through, so undeclared keys must land in ``model_extra`` instead of
    raising.
    """
    definitions: dict[str, Any] = {
        name: (annotation, default) for name, annotation, default in fields
    }
    cls = create_model(tag, __base__=OpenComponent, **definitions)
    # Set after creation, not as a create_model field: a leading underscore is a
    # pydantic private attribute, and this is a plain class-level marker that
    # downstream code reads off the type, never off an instance.
    cls._pjx_classless = True  # pyright: ignore[reportAttributeAccessIssue]
    return cls
