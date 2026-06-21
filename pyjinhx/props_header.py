"""Parse a template's leading ``{#def ... #}`` prop header into a pydantic model.

A classless component template may declare its props in a header that is the
first non-whitespace in the file::

    {#def title: str, count: int = 0, variant: str = "primary" #}

The header is a valid (inert) Jinja comment; pyjinhx parses it out-of-band and
builds a ``BaseComponent`` subclass whose declared props are validated fields.
"""
import ast
import re
from typing import Any, Optional

from pydantic import create_model

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


def _resolve_annotation(node: "ast.expr | None") -> Any:
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
            return Optional[left]
        if left is type(None):
            return Optional[right]
        return Any
    # Optional[T]
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Optional"
    ):
        return Optional[_resolve_annotation(node.slice)]
    return Any


def parse_props_header(source: str) -> "list[tuple[str, Any, Any]] | None":
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
        raise ValueError(f"invalid {{#def#}} header signature {signature!r}: {exc.msg}") from exc
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    arguments = func.args
    if (
        arguments.vararg
        or arguments.kwarg
        or arguments.kwonlyargs
        or arguments.posonlyargs
    ):
        raise ValueError(f"{{#def#}} header may only use simple named props: {signature!r}")
    args = arguments.args
    defaults = arguments.defaults
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


def build_component_model(name: str, source: str) -> "type | None":
    """Build a ``BaseComponent`` subclass from a template's header, or None if absent."""
    fields = parse_props_header(source)
    if fields is None:
        return None
    from pyjinhx.base import BaseComponent

    field_definitions: dict[str, Any] = {
        field_name: (field_type, default) for field_name, field_type, default in fields
    }
    model = create_model(name, __base__=BaseComponent, **field_definitions)
    model._pjx_template = name
    model._pjx_classless = True
    return model
