"""The stub generator: a `.pjx` block's Python as a line-preserving `.pyi`."""

import ast

import pytest

from pyjinhx import sfc, stubgen

CARD = """\
{#python
from pyjinhx import ReactiveComponent

from app.todos import Keys, store


class TodoCount(ReactiveComponent, react={Keys.TODOS}):
    remaining: int = 0

    @classmethod
    def load(cls) -> "TodoCount":
        return cls(remaining=store.remaining())
#}
<div class="counter">{{ remaining }} left</div>
"""


def _stub(source: str) -> str:
    stub = stubgen.generate_stub(source, "card.pjx")
    assert stub is not None
    return stub


def _declarations(source: str) -> list[tuple[str, str, int]]:
    """Every class, def and annotated name outside a function body, with its line."""
    found = []

    def visit(node: ast.AST) -> None:
        match node:
            case ast.ClassDef() | ast.FunctionDef() | ast.AsyncFunctionDef():
                found.append((type(node).__name__, node.name, node.lineno))
            case ast.AnnAssign(target=ast.Name(id=name)):
                found.append(("AnnAssign", name, node.lineno))
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.iter_child_nodes(node):
                visit(child)

    visit(ast.parse(source))
    return sorted(found)


def _document(python: str) -> str:
    return "{#python\n" + python + "#}\n<p></p>\n"


def test_a_document_without_a_block_has_no_stub():
    assert stubgen.generate_stub("<p></p>\n", "card.pjx") is None


def test_declarations_keep_their_line_numbers():
    padded = sfc.python_source(CARD, "card.pjx")
    assert padded is not None
    assert _declarations(_stub(CARD)) == _declarations(padded)


def test_function_bodies_become_an_ellipsis():
    stub = ast.parse(_stub(CARD))
    load = stub.body[-1].body[-1]  # type: ignore[attr-defined]
    assert isinstance(load, ast.FunctionDef)
    assert ast.dump(load.body[0]) == ast.dump(ast.Expr(ast.Constant(...)))


def test_everything_but_function_bodies_is_untouched():
    stub = _stub(CARD)
    assert "class TodoCount(ReactiveComponent, react={Keys.TODOS}):" in stub
    assert "    remaining: int = 0" in stub
    assert "    @classmethod" in stub
    assert '    def load(cls) -> "TodoCount":' in stub
    assert "from app.todos import Keys, store" in stub


def test_the_opener_line_holds_the_marker():
    lines = _stub(CARD).split("\n")
    assert lines[0] == "# pyjinhx.stubgen: generated from card.pjx; do not edit"


def test_the_marker_sits_on_the_openers_line_when_markup_comes_first():
    stub = _stub("<p></p>\n\n" + CARD)
    assert stub.split("\n")[2] == stubgen.marker("card.pjx")


def test_the_stub_ends_on_the_closers_line():
    source = CARD + "<p>{{ 1 }}</p>\n" * 5
    block = sfc.python_block(source, "card.pjx")
    assert block is not None
    assert _stub(source).count("\n") + 1 == block.close_line


@pytest.mark.parametrize(
    "python",
    [
        "def f():\n    x = 1\n    y = (\n        2\n    )\n    return x + y\n",
        "def f(): return 1\n",
        'def f():\n    """Only a docstring."""\n',
        "async def f():\n    await g()\n",
        "def f():\n    def inner():\n        return 1\n    return inner\n",
        "def f(): a = 1; return a\n",
        "def f():\n    return 'é'  # çà\n",
        "def f(): return 'é' + 'ü'\n",
        (
            "class C:\n    @property\n    def p(self) -> int:\n        return 1\n\n"
            "    @classmethod\n    def c(cls): pass\n"
        ),
        "if True:\n    def f():\n        return 1\n",
    ],
)
def test_every_way_of_writing_a_body_keeps_the_lines_after_it(python):
    source = _document(python + "\nclass After:\n    n: int = 1\n")
    stub = _stub(source)
    padded = sfc.python_source(source, "card.pjx")
    assert padded is not None
    assert _declarations(stub) == _declarations(padded)
    assert "return" not in stub and "await" not in stub


def test_a_decorator_and_its_arguments_survive():
    source = _document(
        "class C:\n    @field_validator('a', mode='before')\n"
        "    def v(cls, x):\n        return x\n"
    )
    assert "@field_validator('a', mode='before')" in _stub(source)


def test_a_block_that_is_not_python_is_a_syntax_error_on_its_line():
    with pytest.raises(SyntaxError) as raised:
        stubgen.generate_stub(_document("x = 1\ndef (:\n"), "card.pjx")
    assert raised.value.lineno == 3


def test_generating_runs_nothing(tmp_path):
    sentinel = tmp_path / "ran"
    source = _document(f"open({str(sentinel)!r}, 'w').close()\n")
    stubgen.generate_stub(source, "card.pjx")
    assert not sentinel.exists()
