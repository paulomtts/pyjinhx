"""The fold script: each subcommand's diff, its refusals, and a render round trip.

Every fold is proved the way a user would trust it: render the component from
the files before, fold, render again from the files after, and compare.
"""

import ast
import importlib.util
import re
import sys
import textwrap
from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession, accumulate_assets

SCRIPT = Path(__file__).parent.parent / "scripts" / "fold_components.py"


def load_script():
    spec = importlib.util.spec_from_file_location("fold_components", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fold = load_script()

_modules = iter(range(10_000))


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return path


def render_class(
    module_path: Path, class_name: str, monkeypatch: pytest.MonkeyPatch, **props
) -> str:
    """Import ``module_path`` fresh and render ``class_name`` with its assets.

    Three things legitimately differ once an asset moves into the template and
    are normalised: the path-derived asset token, the newline Jinja keeps
    before an appended block, and the sibling file's trailing newline inside
    the emitted tag. The markup and the asset text are otherwise compared as is.
    """
    name = f"fold_probe_{next(_modules)}"
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    html = render(getattr(module, class_name)(**props), session)
    html = re.sub(r'data-pjx-asset="[0-9a-f]+"', 'data-pjx-asset=""', html)
    html = re.sub(r"\s+(?=<(?:style|script)\b)", "", html)
    return re.sub(
        r"(<(style|script)[^>]*>)\s*(.*?)\s*(</\2>)", r"\1\3\4", html, flags=re.DOTALL
    )


def run(*args: object, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = fold.main([str(arg) for arg in args])
    return code, capsys.readouterr().out


@pytest.fixture(autouse=True)
def empty_registry():
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = {}


CARD_PY = """
    from pyjinhx import BaseComponent


    class Card(BaseComponent):
        title: str
"""
CARD_PJX = '<div class="card">{{ title }}</div>\n'
CARD_CSS = ".card { color: red; }\n"


def make_card(tmp_path: Path, pjx: str = CARD_PJX) -> Path:
    write(tmp_path / "card.py", CARD_PY)
    write(tmp_path / "card.pjx", pjx)
    return tmp_path / "card.py"


# --- assets -----------------------------------------------------------------


def test_assets_folds_a_sibling_css_into_a_block_and_deletes_it(
    tmp_path, monkeypatch, capsys
):
    module = make_card(tmp_path)
    css = write(tmp_path / "card.css", CARD_CSS)
    before = render_class(module, "Card", monkeypatch, title="hi")

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert not css.exists()
    assert "{#css\n.card { color: red; }\n#}" in (tmp_path / "card.pjx").read_text()
    assert render_class(module, "Card", monkeypatch, title="hi") == before
    assert ".card { color: red; }" in before
    assert "1 folded" in out


def test_assets_folds_a_sibling_js_beside_an_existing_css_block(
    tmp_path, monkeypatch, capsys
):
    module = make_card(tmp_path, CARD_PJX + "{#css\n.card { top: 0; }\n#}\n")
    write(tmp_path / "card.js", "console.log('card');\n")
    before = render_class(module, "Card", monkeypatch, title="hi")

    code, _ = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert not (tmp_path / "card.js").exists()
    assert render_class(module, "Card", monkeypatch, title="hi") == before


def test_assets_dry_run_prints_a_diff_and_writes_nothing(tmp_path, capsys):
    make_card(tmp_path)
    css = write(tmp_path / "card.css", CARD_CSS)

    code, out = run("assets", tmp_path, capsys=capsys)

    assert code == 0
    assert css.exists()
    assert (tmp_path / "card.pjx").read_text() == CARD_PJX
    assert "+{#css" in out
    assert "dry run" in out


def test_assets_is_idempotent(tmp_path, capsys):
    make_card(tmp_path)
    write(tmp_path / "card.css", CARD_CSS)
    run("assets", tmp_path, "--write", capsys=capsys)
    folded = (tmp_path / "card.pjx").read_text()

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert (tmp_path / "card.pjx").read_text() == folded
    assert "0 folded" in out


def test_assets_refuses_a_body_holding_a_comment_terminator(tmp_path, capsys):
    make_card(tmp_path)
    css = write(tmp_path / "card.css", "a::after { content: '#}'; }\n")

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "#}" in out and "card.css" in out


def test_assets_refuses_when_the_template_already_has_that_block(tmp_path, capsys):
    make_card(tmp_path, CARD_PJX + "{#css\n.x {}\n#}\n")
    css = write(tmp_path / "card.css", CARD_CSS)

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "already" in out


def test_assets_refuses_an_asset_a_subclass_with_its_own_template_inherits(
    tmp_path, capsys
):
    make_card(tmp_path)
    write(
        tmp_path / "fancy_card.py",
        """
        from card import Card


        class FancyCard(Card):
            pass
        """,
    )
    write(tmp_path / "fancy_card.pjx", "<section>{{ title }}</section>\n")
    css = write(tmp_path / "card.css", CARD_CSS)

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "FancyCard" in out


def test_assets_still_processes_the_rest_after_a_refusal(tmp_path, capsys):
    make_card(tmp_path)
    write(tmp_path / "card.css", "a { content: '#}'; }\n")
    write(tmp_path / "chip.pjx", "<i></i>\n")
    write(tmp_path / "chip.js", "go();\n")

    code, _ = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert not (tmp_path / "chip.js").exists()
    assert "{#js\ngo();\n#}" in (tmp_path / "chip.pjx").read_text()


# --- template ---------------------------------------------------------------


def test_template_folds_the_pjx_into_the_class_as_its_last_statement(
    tmp_path, monkeypatch, capsys
):
    module = make_card(tmp_path)
    before = render_class(module, "Card", monkeypatch, title="hi")

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    folded = module.read_text()
    assert code == 0
    assert not (tmp_path / "card.pjx").exists()
    assert folded.endswith(
        '    title: str\n\n    template = r"""\n'
        '    <div class="card">{{ title }}</div>\n    """\n'
    )
    ast.parse(folded)
    assert render_class(module, "Card", monkeypatch, title="hi") == before
    assert "1 folded" in out


def test_template_keeps_nested_markup_indentation(tmp_path, monkeypatch, capsys):
    module = make_card(
        tmp_path, '<div class="card">\n  <h1>{{ title }}</h1>\n\n  <p>x</p>\n</div>\n'
    )
    before = render_class(module, "Card", monkeypatch, title="hi")

    run("template", tmp_path, "--write", capsys=capsys)

    assert render_class(module, "Card", monkeypatch, title="hi") == before


def test_template_replaces_a_pass_body(tmp_path, monkeypatch, capsys):
    module = write(
        tmp_path / "badge.py",
        """
        from pyjinhx import BaseComponent


        class Badge(BaseComponent):
            pass
        """,
    )
    write(tmp_path / "badge.pjx", "<b>badge</b>\n")
    before = render_class(module, "Badge", monkeypatch)

    run("template", tmp_path, "--write", capsys=capsys)

    assert "pass" not in module.read_text()
    assert render_class(module, "Badge", monkeypatch) == before


def test_template_falls_back_to_single_quotes_when_the_content_has_triple_double(
    tmp_path, monkeypatch, capsys
):
    module = make_card(tmp_path, '<div title=\'"""\'>{{ title }}</div>\n')
    before = render_class(module, "Card", monkeypatch, title="hi")

    code, _ = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert "r'''" in module.read_text()
    assert render_class(module, "Card", monkeypatch, title="hi") == before


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("{# \"\"\" ''' #}<i></i>\n", "both"),
        ("<i></i>{# a \\\n", "backslash"),
        ("  <i></i>\n  <b></b>\n", "indentation"),
    ],
)
def test_template_refuses_content_a_raw_string_cannot_hold(
    tmp_path, capsys, content, reason
):
    module = make_card(tmp_path)
    (tmp_path / "card.pjx").write_text(content)  # unlike write(), keeps indentation
    original = module.read_text()

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert reason in out
    assert module.read_text() == original
    assert (tmp_path / "card.pjx").exists()


def test_template_refuses_a_second_class_of_the_same_name(tmp_path, capsys):
    module = make_card(tmp_path)
    module.write_text(
        module.read_text()
        + "\n\nif True:\n    class Card(BaseComponent):\n        title: str\n"
    )

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "more than one class named Card" in out


def test_template_refuses_a_class_that_already_has_a_template(tmp_path, capsys):
    module = make_card(tmp_path)
    module.write_text(module.read_text() + '\n    template = "<i></i>"\n')

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "already assigns" in out
    assert (tmp_path / "card.pjx").exists()


def test_template_is_idempotent_and_leaves_subclasses_rendering(
    tmp_path, monkeypatch, capsys
):
    module = make_card(tmp_path)
    module.write_text(module.read_text() + "\n\nclass LoudCard(Card):\n    pass\n")
    before = render_class(module, "LoudCard", monkeypatch, title="hi")
    run("template", tmp_path, "--write", capsys=capsys)
    folded = module.read_text()

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert module.read_text() == folded
    assert "0 folded" in out
    assert render_class(module, "LoudCard", monkeypatch, title="hi") == before


def test_template_dry_run_prints_a_diff_and_writes_nothing(tmp_path, capsys):
    module = make_card(tmp_path)

    code, out = run("template", tmp_path, capsys=capsys)

    assert code == 0
    assert module.read_text() == textwrap.dedent(CARD_PY).lstrip("\n")
    assert (tmp_path / "card.pjx").exists()
    assert '+    template = r"""' in out
    assert "+++ /dev/null" in out
    assert "dry run" in out
