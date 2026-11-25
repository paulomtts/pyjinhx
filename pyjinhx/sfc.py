"""Single-file components: reading a class's inline template out of its module.

A component may carry its template as a string instead of an adjacent `.pjx`
file::

    class Badge(BaseComponent):
        label: str

        template = \"\"\"
        <span class="badge">{{ label }}</span>
        \"\"\"

Import-pure — stdlib only. The module source is parsed, never executed, and
the imported class is never consulted, so a template edited on disk is seen
without re-importing anything.
"""

import ast
import textwrap
import threading
from pathlib import Path


def _template_value(node: ast.ClassDef) -> ast.expr | None:
    """The expression a class body assigns to ``template``, or None.

    The last assignment wins, as it does when Python runs the body.
    """
    value = None
    for statement in node.body:
        match statement:
            case ast.Assign(targets=targets) if any(
                isinstance(target, ast.Name) and target.id == "template"
                for target in targets
            ):
                value = statement.value
            case ast.AnnAssign(target=ast.Name(id="template"), value=ast.expr()):
                value = statement.value
    return value


# The last parse of each module, keyed by filename and checked against the
# source it was made from. A template is read several times as its class
# registers and renders, so without this a module of N components is parsed
# N times over. Each entry is built whole and then swapped in under the lock.
_parsed: dict[str, tuple[str, dict[str, list[ast.expr]]]] = {}
_parsed_lock = threading.Lock()


def _templates_in(module_source: str, filename: str) -> dict[str, list[ast.expr]]:
    """Every class in ``module_source`` that assigns ``template``, by class name."""
    with _parsed_lock:
        cached = _parsed.get(filename)
    if cached is not None and cached[0] == module_source:
        return cached[1]
    found: dict[str, list[ast.expr]] = {}
    for node in ast.walk(ast.parse(module_source, filename=filename)):
        if isinstance(node, ast.ClassDef):
            value = _template_value(node)
            if value is not None:
                found.setdefault(node.name, []).append(value)
    with _parsed_lock:
        _parsed[filename] = (module_source, found)
    return found


def extract_template(
    module_source: str, class_name: str, filename: str = "<unknown>"
) -> str:
    """The inline template of ``class_name``, as Jinja source.

    Common indentation and blank edges are removed, so the template may be
    indented along with the class body. Every remaining line sits on the same
    line number it has in ``module_source``.

    Raises:
        SyntaxError: ``module_source`` is not valid Python.
        ValueError: No class of that name assigns ``template``, more than one
            does, or the value is anything but one string literal.
    """
    values = _templates_in(module_source, filename).get(class_name, [])
    if not values:
        raise ValueError(
            f"{filename}: class {class_name} has no inline template: its body "
            f"assigns no `template` string."
        )
    if len(values) > 1:
        lines = ", ".join(str(line) for line in sorted(v.lineno for v in values))
        raise ValueError(
            f"{filename}: classes named {class_name} assign `template` on lines "
            f"{lines}. An inline template is found by its class's name, so "
            f"rename one."
        )
    value = values[0]
    match value:
        case ast.Constant(value=str() as text):
            body = textwrap.dedent(text)
        case _:
            raise ValueError(
                f"{filename}, line {value.lineno}: {class_name}.template must "
                f"be a plain string literal. It is read from the source text, "
                f"so an f-string, a concatenation or a name cannot be used."
            )
    content = body.lstrip()
    skipped_lines = body[: len(body) - len(content)].count("\n")
    # A Jinja comment renders as nothing but its newlines are still counted,
    # so padding with one makes template line N the module's line N. Errors
    # and tracebacks then point into the .py file with no source map.
    padding = "\n" * (value.lineno - 1 + skipped_lines)
    return f"{{#{padding}#}}{content.rstrip()}"


def read_document(template_path: Path, inline_class: str | None) -> str:
    """The pjx document a component renders: a ``.pjx`` file's text, or the
    inline template of ``inline_class`` read out of the ``.py`` module at
    ``template_path``.

    The one way template source is read, so a ``.py`` module is never
    mistaken for a document.
    """
    source = template_path.read_text(encoding="utf-8")
    if inline_class is None:
        return source
    return extract_template(source, inline_class, str(template_path))
