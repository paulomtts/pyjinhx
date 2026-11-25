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


def _template_value(tree: ast.Module, class_name: str) -> ast.expr | None:
    """The expression assigned to ``template`` in the body of ``class_name``."""
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == class_name):
            continue
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                targets = statement.targets
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
            else:
                continue
            if any(isinstance(t, ast.Name) and t.id == "template" for t in targets):
                return statement.value
    return None


def extract_template(module_source: str, class_name: str) -> str:
    """The inline template of ``class_name``, as Jinja source.

    Common indentation and blank edges are removed, so the template may be
    indented along with the class body. Every remaining line sits on the same
    line number it has in ``module_source``.

    Raises:
        ValueError: The class assigns no ``template``, or assigns something
            other than one string literal.
    """
    value = _template_value(ast.parse(module_source), class_name)
    if value is None:
        raise ValueError(
            f"class {class_name} has no inline template: its body assigns no "
            f"`template` string."
        )
    if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
        raise ValueError(
            f"line {value.lineno}: {class_name}.template must be a plain string "
            f"literal. It is read from the source text, so an f-string, a "
            f"concatenation or a name cannot be used."
        )
    body = textwrap.dedent(value.value)
    content = body.lstrip()
    skipped_lines = body[: len(body) - len(content)].count("\n")
    # A Jinja comment renders as nothing but its newlines are still counted,
    # so padding with one makes template line N the module's line N. Errors
    # and tracebacks then point into the .py file with no source map.
    padding = "\n" * (value.lineno - 1 + skipped_lines)
    return f"{{#{padding}#}}{content.rstrip()}"
