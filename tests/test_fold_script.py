"""The fold script: each subcommand's diff, its refusals, and a render round trip.

Every fold is proved the way a user would trust it: render the component from
the files before, fold, render again from the files after, and compare.
"""

import ast
import importlib.util
import re
import subprocess
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


# --- assets inside an inline template ----------------------------------------


CHIP_PY = '''
    from pyjinhx import BaseComponent


    class Chip(BaseComponent):
        label: str

        template = r"""
        <i class="chip">{{ label }}</i>
        """
'''


def test_assets_folds_into_an_inline_template_string(tmp_path, monkeypatch, capsys):
    module = write(tmp_path / "chip.py", CHIP_PY)
    css = write(tmp_path / "chip.css", ".chip { content: '\\2022'; }\n")
    before = render_class(module, "Chip", monkeypatch, label="x")

    code, _ = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert not css.exists()
    ast.parse(module.read_text())
    assert module.read_text().endswith(
        '    template = r"""\n    <i class="chip">{{ label }}</i>\n'
        '    {#css\n    .chip { content: \'\\2022\'; }\n    #}\n    """\n'
    )
    assert render_class(module, "Chip", monkeypatch, label="x") == before


def test_assets_refuses_a_backslash_asset_for_a_non_raw_template(tmp_path, capsys):
    module = write(tmp_path / "chip.py", CHIP_PY.replace('r"""', '"""'))
    css = write(tmp_path / "chip.css", ".chip { content: '\\2022'; }\n")

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "raw" in out
    assert "css" not in module.read_text().split("template")[1]


def test_assets_refuses_a_template_that_is_not_triple_quoted(tmp_path, capsys):
    write(
        tmp_path / "chip.py",
        """
        from pyjinhx import BaseComponent


        class Chip(BaseComponent):
            template = "<i></i>"
        """,
    )
    css = write(tmp_path / "chip.css", ".chip {}\n")

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "triple-quoted" in out


def test_assets_refuses_an_inline_template_that_already_has_the_block(tmp_path, capsys):
    write(
        tmp_path / "chip.py",
        CHIP_PY.replace('    """\n', '    {#css\n    .a {}\n    #}\n    """\n'),
    )
    css = write(tmp_path / "chip.css", ".chip {}\n")

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "already" in out


def test_assets_folds_css_and_js_into_one_inline_template(
    tmp_path, monkeypatch, capsys
):
    module = write(tmp_path / "chip.py", CHIP_PY)
    write(tmp_path / "chip.css", ".chip {}\n")
    write(tmp_path / "chip.js", "go();\n")
    before = render_class(module, "Chip", monkeypatch, label="x")

    code, _ = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert render_class(module, "Chip", monkeypatch, label="x") == before
    assert "go();" in before and ".chip {}" in before


# --- declass ----------------------------------------------------------------

FIELDS_PY = """
    from typing import Literal

    from pyjinhx import BaseComponent


    class Card(BaseComponent):
        \"\"\"A card.\"\"\"

        title: str
        count: int = 0
        tone: Literal["calm", "loud"] = "calm"
        tags: list[str] = []
"""
FIELDS_PJX = (
    '<div class="card {{ tone }}">{{ title }} {{ count }} {{ tags|join(",") }}</div>\n'
)


def render_tag(template_dir: Path, **props) -> str:
    """Render ``<Card>`` the way an app with only the .pjx does."""
    from pyjinhx import component

    cls = component("Card", template_dir=template_dir)
    session = RenderSession()
    return render(cls(**props), session)  # pyright: ignore[reportCallIssue]


def test_declass_writes_a_header_deletes_the_py_and_renders_the_same(
    tmp_path, monkeypatch, capsys
):
    module = write(tmp_path / "card.py", FIELDS_PY)
    write(tmp_path / "card.pjx", FIELDS_PJX)
    props = {"title": "hi", "count": 2, "tags": ["a", "b"]}
    before = render_class(module, "Card", monkeypatch, **props)

    code, out = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert not module.exists()
    assert (tmp_path / "card.pjx").read_text() == (
        "{#def title: str,\n"
        "      count: int = 0,\n"
        "      tone: Literal['calm', 'loud'] = 'calm',\n"
        "      tags: list[str] = [] #}\n" + FIELDS_PJX
    )
    # The header's own line break is the only difference a fold may leave.
    assert render_tag(tmp_path, **props).removeprefix("\n") == before
    assert "1 folded" in out


def test_declass_turns_auto_id_false_into_a_required_id(tmp_path, capsys):
    write(
        tmp_path / "card.py",
        """
        from pyjinhx import BaseComponent


        class Card(BaseComponent):
            auto_id = False
            title: str
        """,
    )
    write(tmp_path / "card.pjx", "<i>{{ title }}</i>\n")

    run("declass", tmp_path, "--write", capsys=capsys)

    assert (
        (tmp_path / "card.pjx").read_text().startswith("{#def id: str, title: str #}")
    )


def test_declass_names_imports_the_header_cannot_see(tmp_path, capsys):
    write(
        tmp_path / "card.py",
        """
        from datetime import datetime

        from app.consts import PAGE_SIZE
        from app.models import Color, make_tags
        from pyjinhx import BaseComponent, Slot


        class Card(BaseComponent):
            when: datetime
            body: Slot
            size: int = PAGE_SIZE
            color: Color = Color.RED
        """,
    )
    write(tmp_path / "card.pjx", "<i></i>\n")

    code, _ = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 0
    header = (tmp_path / "card.pjx").read_text().split(" #}")[0]
    assert header == (
        "{#def when: datetime.datetime,\n"
        "      body: Slot,\n"
        "      size: int = app.consts.PAGE_SIZE,\n"
        "      color: app.models.Color = app.models.Color.RED"
    )


def test_declass_writes_a_default_factory_as_the_header_default(tmp_path, capsys):
    write(
        tmp_path / "card.py",
        """
        from pydantic import Field

        from app.models import make_tags
        from pyjinhx import BaseComponent


        class Card(BaseComponent):
            attrs: dict[str, str] = Field(default_factory=dict)
            rows: list[str] = Field(default_factory=list)
            tags: list[str] = Field(default_factory=make_tags)
        """,
    )
    write(tmp_path / "card.pjx", "<i></i>\n")

    code, _ = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 0
    header = (tmp_path / "card.pjx").read_text().split(" #}")[0]
    assert header == (
        "{#def attrs: dict[str, str] = {},\n"
        "      rows: list[str] = [],\n"
        "      tags: list[str] = app.models.make_tags()"
    )


def test_declass_writes_an_object_annotation_as_any(tmp_path, capsys):
    write(
        tmp_path / "card.py",
        """
        from pyjinhx import BaseComponent


        class Card(BaseComponent):
            value: object = None
        """,
    )
    write(tmp_path / "card.pjx", "<i>{{ value }}</i>\n")

    code, _ = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert (tmp_path / "card.pjx").read_text().startswith("{#def value: Any = None #}")


def test_declass_reports_every_reference_under_the_root(tmp_path, capsys):
    components = tmp_path / "components"
    write(components / "card.py", FIELDS_PY)
    write(components / "card.pjx", FIELDS_PJX)
    write(
        tmp_path / "views.py", "from components.card import Card\n\nCard(title='x')\n"
    )
    write(tmp_path / "other.py", "print('nothing here')\n")

    code, out = run("declass", components, "--root", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert "views.py:1:" in out and "views.py:3:" in out
    assert "other.py" not in out
    assert (tmp_path / "views.py").read_text().startswith("from components.card")


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ("title: str\n    def shout(self): ...", "shout"),
        ("title: str\n    @property\n    def loud(self): ...", "loud"),
        (
            (
                "title: str\n    @field_validator('title')\n    @classmethod\n"
                "    def check(cls, v): return v"
            ),
            "check",
        ),
        ("title: str\n    model_config = {'frozen': True}", "model_config"),
        ("title: str = DEFAULT", "DEFAULT"),
        ("title: str = Field(default='x')", "Field"),
        ("title: Local", "Local"),
        ("title: 'str'", "string annotation"),
    ],
)
def test_declass_refuses_a_class_that_needs_python(tmp_path, capsys, body, reason):
    module = write(
        tmp_path / "card.py",
        "from pydantic import Field, field_validator\n"
        "from pyjinhx import BaseComponent\n\n"
        "DEFAULT = 'x'\n\n\nclass Local: ...\n\n\n"
        f"class Card(BaseComponent):\n    {body}\n",
    )
    write(tmp_path / "card.pjx", "<i></i>\n")

    code, out = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert reason in out
    assert module.exists()
    assert (tmp_path / "card.pjx").read_text() == "<i></i>\n"


def test_declass_refuses_a_class_with_keywords_a_decorator_or_another_base(
    tmp_path, capsys
):
    write(
        tmp_path / "a.py",
        "from pyjinhx import BaseComponent\n\n\n"
        "class A(BaseComponent, metaclass=type):\n    x: str\n",
    )
    write(
        tmp_path / "b.py",
        "from pyjinhx import BaseComponent\n\n\n@decorate\nclass B(BaseComponent):\n    x: str\n",
    )
    write(tmp_path / "c.py", "from app import Base\n\n\nclass C(Base):\n    x: str\n")
    for stem in "abc":
        write(tmp_path / f"{stem}.pjx", "<i></i>\n")

    code, out = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "3 refused" in out
    assert all((tmp_path / f"{stem}.py").exists() for stem in "abc")


def test_declass_refuses_a_module_that_holds_more_than_the_class(tmp_path, capsys):
    module = write(
        tmp_path / "card.py", textwrap.dedent(FIELDS_PY) + "\n\nVERSION = 1\n"
    )
    write(tmp_path / "card.pjx", FIELDS_PJX)

    code, out = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "VERSION" in out or "Assign" in out
    assert module.exists()


def test_declass_refuses_without_a_template_or_when_a_header_exists(tmp_path, capsys):
    write(tmp_path / "card.py", FIELDS_PY)
    write(tmp_path / "chip.py", FIELDS_PY.replace("Card", "Chip"))
    write(tmp_path / "chip.pjx", "{#def label: str #}\n<i></i>\n")

    code, out = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "no card.pjx" in out
    assert "already has a {#def#} header" in out


def test_declass_is_idempotent_and_dry_runs_by_default(tmp_path, capsys):
    module = write(tmp_path / "card.py", FIELDS_PY)
    write(tmp_path / "card.pjx", FIELDS_PJX)

    code, out = run("declass", tmp_path, capsys=capsys)

    assert code == 0
    assert module.exists()
    assert (tmp_path / "card.pjx").read_text() == FIELDS_PJX
    assert "+{#def title: str" in out and "+++ /dev/null" in out
    assert "dry run" in out

    run("declass", tmp_path, "--write", capsys=capsys)
    code, out = run("declass", tmp_path, "--write", capsys=capsys)
    assert code == 0 and "0 folded" in out


def test_declass_refuses_a_required_field_after_a_defaulted_one(tmp_path, capsys):
    write(
        tmp_path / "card.py",
        """
        from pyjinhx import BaseComponent


        class Card(BaseComponent):
            tone: str = "calm"
            title: str
        """,
    )
    write(tmp_path / "card.pjx", "<i></i>\n")

    code, out = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "without a default" in out


# --- the command line ---------------------------------------------------------


def test_the_script_runs_as_a_command_and_exits_non_zero_on_a_refusal(tmp_path):
    make_card(tmp_path)
    write(tmp_path / "card.css", "a { content: '#}'; }\n")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "assets", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "refused" in result.stdout
    assert (tmp_path / "card.css").exists()


def test_only_the_given_paths_are_touched(tmp_path, capsys):
    for name in ("mine", "theirs"):
        write(tmp_path / name / "card.py", CARD_PY)
        write(tmp_path / name / "card.pjx", CARD_PJX)
        write(tmp_path / name / "card.css", CARD_CSS)

    run("assets", tmp_path / "mine", "--write", capsys=capsys)
    run("template", tmp_path / "mine", "--write", capsys=capsys)

    assert (tmp_path / "theirs" / "card.css").exists()
    assert (tmp_path / "theirs" / "card.pjx").read_text() == CARD_PJX
    assert not (tmp_path / "mine" / "card.pjx").exists()
