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
    fields: list[tuple[str, Any, Any]] = []
    for arg in func.args.args:
        fields.append((arg.arg, _resolve_annotation(arg.annotation), ...))
    return fields
