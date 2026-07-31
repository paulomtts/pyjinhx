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
    tree = ast.parse(f"def __pjx_props__({signature}): pass")
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    arguments = func.args
    args = arguments.args
    defaults = arguments.defaults
    # Defaults bind to the *last* N params, so this offset maps index -> default.
    offset = len(args) - len(defaults)
    fields: list[tuple[str, Any, Any]] = []
    for index, arg in enumerate(args):
        annotation = _resolve_annotation(arg.annotation)
        if index >= offset:
            default = ast.literal_eval(defaults[index - offset])
        else:
            default = ...
        fields.append((arg.arg, annotation, default))
    return fields
