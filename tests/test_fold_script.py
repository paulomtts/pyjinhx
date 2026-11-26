"""The fold script: each subcommand's diff, its refusals, and a render round trip.

Every fold is proved the way a user would trust it: render the component from
the files before, fold, render again from the files after, and compare.
"""

import ast
import importlib
import importlib.util
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from pyjinhx.components import discovery
from pyjinhx.rendering.pipeline import render
from pyjinhx.rendering.session import RenderSession, accumulate_assets

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


def test_assets_refuses_when_an_inheriting_subclass_has_its_own_sibling_file(
    tmp_path, capsys
):
    """Its own .css shadows the parent's file but would not shadow a block."""
    make_card(tmp_path)
    write(
        tmp_path / "fancy_card.py",
        """
        from card import Card


        class FancyCard(Card):
            pass
        """,
    )
    write(tmp_path / "fancy_card.css", ".fancy {}\n")
    css = write(tmp_path / "card.css", CARD_CSS)

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "FancyCard" in out and "fancy_card.css" in out


def test_assets_reports_every_line_under_the_root_that_names_the_file(tmp_path, capsys):
    components = tmp_path / "components"
    make_card(components)
    write(components / "card.css", CARD_CSS)
    write(tmp_path / "views.py", "BORROWED = HERE / 'card.css'\n")
    write(tmp_path / "tests" / "test_card.py", "x = 1\nread('card.css')\n")
    write(tmp_path / "other.py", "print('card.js')\n")

    code, out = run("assets", components, "--root", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert "views.py:1:" in out and "test_card.py:2:" in out
    assert "other.py" not in out
    assert "2 references" in out
    assert not (components / "card.css").exists()


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


def test_template_sees_a_template_assigned_alongside_another_name(tmp_path, capsys):
    """Found the way pyjinhx finds it, so the fold never adds a second one."""
    module = make_card(tmp_path)
    module.write_text(module.read_text() + '\n    template = alias = "<i></i>"\n')

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "already assigns" in out


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


def test_declass_writes_a_tuple_annotation(tmp_path, capsys):
    write(
        tmp_path / "card.py",
        """
        from pyjinhx import BaseComponent


        class Card(BaseComponent):
            pair: tuple[str, int]
            sizes: tuple[int, ...] = ()
            more: tuple[int, ...] | None = None
        """,
    )
    write(tmp_path / "card.pjx", "<i></i>\n")

    code, _ = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 0
    header = (tmp_path / "card.pjx").read_text()
    assert "pair: tuple[str, int]" in header
    assert "sizes: tuple[int, ...] = ()" in header
    assert "more: tuple[int, ...] | None = None" in header


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


def test_declass_refuses_a_class_that_is_subclassed_under_the_root(tmp_path, capsys):
    components = tmp_path / "components"
    module = write(components / "card.py", FIELDS_PY)
    write(components / "card.pjx", FIELDS_PJX)
    write(
        tmp_path / "views.py",
        "from components.card import Card\n\n\nclass Big(Card):\n    pass\n",
    )

    code, out = run("declass", components, "--root", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "views.py:4" in out and "Big" in out
    assert module.exists()


def test_declass_refuses_a_class_subclassed_under_the_given_paths(tmp_path, capsys):
    module = write(tmp_path / "card.py", FIELDS_PY)
    write(tmp_path / "card.pjx", FIELDS_PJX)
    write(
        tmp_path / "big.py",
        "from card import Card\n\n\nclass Big(Card):\n    pass\n",
    )

    code, out = run("declass", tmp_path, capsys=capsys)

    assert code == 1
    assert "big.py:4" in out
    assert module.exists()


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


def test_declass_refuses_a_called_default(tmp_path, capsys):
    """A class body calls it once; a header would call it per instance."""
    module = write(
        tmp_path / "card.py",
        "import datetime\n\nfrom pyjinhx import BaseComponent\n\n\n"
        "class Card(BaseComponent):\n"
        "    at: datetime.datetime = datetime.datetime.now()\n",
    )
    write(tmp_path / "card.pjx", "<i></i>\n")

    code, out = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "datetime.datetime.now()" in out and "once" in out
    assert module.exists()


def test_declass_explains_that_field_constraints_are_not_expressible(tmp_path, capsys):
    module = write(
        tmp_path / "card.py",
        "from pydantic import Field\nfrom pyjinhx import BaseComponent\n\n\n"
        "class Card(BaseComponent):\n    title: str = Field(min_length=1)\n",
    )
    write(tmp_path / "card.pjx", "<i></i>\n")

    code, out = run("declass", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "Field(min_length=1)" in out and "constraints" in out
    assert "once" not in out
    assert module.exists()


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


# --- pyblock ----------------------------------------------------------------

_packages = iter(range(10_000))


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh importable package directory under ``tmp_path``."""
    directory = tmp_path / f"fold_pkg_{next(_packages)}"
    write(directory / "__init__.py", "")
    monkeypatch.syspath_prepend(str(tmp_path))
    return directory


def import_fresh(module: str, monkeypatch: pytest.MonkeyPatch):
    """``module`` imported by name, forgotten again when the test ends."""
    importlib.invalidate_caches()
    for name in [n for n in sys.modules if n == module or n.startswith(f"{module}.")]:
        monkeypatch.delitem(sys.modules, name)
    imported = importlib.import_module(module)
    monkeypatch.delitem(sys.modules, module)
    return imported


def test_pyblock_folds_the_module_into_its_pjx_and_renders_the_same(
    package, monkeypatch, capsys
):
    write(package / "card.py", CARD_PY)
    write(package / "card.pjx", CARD_PJX)
    write(package / "card.css", CARD_CSS)
    module = f"{package.name}.card"
    before = import_fresh(module, monkeypatch).Card(id="c", title="hi").render()

    code, out = run("pyblock", package, "--write", capsys=capsys)

    assert code == 0
    assert not (package / "card.py").exists()
    assert (package / "card.css").exists()
    folded = (package / "card.pjx").read_text()
    assert (
        folded
        == "{#python\n" + textwrap.dedent(CARD_PY).lstrip("\n") + "#}\n" + CARD_PJX
    )
    assert import_fresh(module, monkeypatch).Card(id="c", title="hi").render() == before
    assert "1 folded" in out


def test_pyblock_folds_a_module_with_imports_helpers_and_a_relative_import(
    package, monkeypatch, capsys
):
    write(package / "util.py", "SUFFIX = '!'\n")
    write(
        package / "card.py",
        '''
        """A card."""
        from __future__ import annotations

        from pyjinhx import BaseComponent

        from .util import SUFFIX


        def shout(text: str) -> str:
            return text + SUFFIX


        class Card(BaseComponent):
            title: str

            def model_post_init(self, context) -> None:
                self.title = shout(self.title)
        ''',
    )
    write(package / "card.pjx", "<b>{{ title }}</b>\n")
    module = f"{package.name}.card"
    before = import_fresh(module, monkeypatch).Card(id="c", title="hi").render()

    code, _ = run("pyblock", package, "--write", capsys=capsys)

    assert code == 0
    assert import_fresh(module, monkeypatch).Card(id="c", title="hi").render() == before


def test_pyblock_reports_a_second_class_that_keeps_its_own_pjx(
    package, monkeypatch, capsys
):
    write(
        package / "card.py",
        CARD_PY + "\n\n    class Chip(BaseComponent):\n        label: str = ''\n",
    )
    write(package / "card.pjx", CARD_PJX)
    write(package / "chip.pjx", "<i>{{ label }}</i>\n")

    code, out = run("pyblock", package, "--write", capsys=capsys)

    assert code == 0
    assert "Chip keeps its chip.pjx" in out
    assert (package / "chip.pjx").exists()
    chip = import_fresh(f"{package.name}.card", monkeypatch).Chip
    assert chip(id="x", label="a").render() == "<i>a</i>"


def refused(tmp_path: Path, reason: str, capsys, *paths: Path) -> None:
    before = {p: p.read_text() for p in tmp_path.rglob("*") if p.is_file()}
    code, out = run("pyblock", *(paths or (tmp_path,)), "--write", capsys=capsys)
    assert code == 1
    assert "refused" in out and reason in out
    assert {p: p.read_text() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_pyblock_refuses_source_with_a_block_closer_and_names_the_line(
    tmp_path, capsys
):
    make_card(tmp_path)
    (tmp_path / "card.py").write_text(
        textwrap.dedent(CARD_PY).lstrip("\n") + "\nEND = '#}'\n"
    )
    refused(tmp_path, "`#}` on line 7", capsys)


def test_pyblock_refuses_a_module_with_no_class_named_for_it(tmp_path, capsys):
    write(tmp_path / "other.py", CARD_PY)
    write(tmp_path / "other.pjx", CARD_PJX)
    refused(tmp_path, "no class named for other", capsys, tmp_path / "other.py")


def test_pyblock_refuses_a_package_init(tmp_path, capsys):
    write(tmp_path / "__init__.py", CARD_PY)
    refused(tmp_path, "__init__.py", capsys, tmp_path / "__init__.py")


def test_pyblock_refuses_a_class_without_a_pjx_of_its_own(tmp_path, capsys):
    write(tmp_path / "card.py", CARD_PY)
    refused(
        tmp_path,
        "there is no card.pjx beside it",
        capsys,
        tmp_path / "card.py",
    )


def test_pyblock_walk_skips_a_component_class_with_no_pjx_beside_it(tmp_path, capsys):
    write(tmp_path / "user.py", CARD_PY.replace("Card", "User"))

    code, out = run("pyblock", tmp_path, capsys=capsys)

    assert code == 0 and "0 folded, 0 refused" in out


def test_pyblock_refuses_a_class_that_assigns_its_template(tmp_path, capsys):
    make_card(tmp_path)
    write(
        tmp_path / "card.py",
        CARD_PY + "        template = '<i></i>'\n",
    )
    refused(tmp_path, "assigns its own `template`", capsys)


def test_pyblock_refuses_a_pjx_that_already_holds_a_python_block(tmp_path, capsys):
    make_card(tmp_path, "{#python\nx = 1\n#}\n" + CARD_PJX)
    refused(tmp_path, "already has a {#python block", capsys)


def test_pyblock_refuses_a_pjx_with_a_def_header(tmp_path, capsys):
    make_card(tmp_path, "{#def title: str #}\n" + CARD_PJX)
    refused(tmp_path, "already has a {#def#} header", capsys)


def test_pyblock_refuses_a_pjx_with_no_markup(tmp_path, capsys):
    make_card(tmp_path, "{# only a comment #}\n")
    refused(tmp_path, "has no markup", capsys)


def test_pyblock_refuses_when_a_directory_would_shadow_the_module(tmp_path, capsys):
    make_card(tmp_path)
    (tmp_path / "card").mkdir()
    refused(tmp_path, "a card/ directory", capsys)


def test_pyblock_reports_every_line_under_the_root_that_names_the_file(
    tmp_path, capsys
):
    components = tmp_path / "components"
    make_card(components)
    write(tmp_path / "setup.py", "FILES = ['components/card.py']\n")
    write(tmp_path / "other.py", "print('nothing')\n")

    code, out = run("pyblock", components, "--root", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert "setup.py:1:" in out and "other.py" not in out
    assert "1 references" in out


def test_pyblock_dry_run_writes_nothing_and_a_second_write_is_a_no_op(tmp_path, capsys):
    make_card(tmp_path)

    code, out = run("pyblock", tmp_path, capsys=capsys)

    assert code == 0
    assert "+{#python" in out and "-class Card" in out
    assert (tmp_path / "card.py").exists()
    assert (tmp_path / "card.pjx").read_text() == CARD_PJX

    run("pyblock", tmp_path, "--write", capsys=capsys)
    folded = (tmp_path / "card.pjx").read_text()
    code, out = run("pyblock", tmp_path, "--write", capsys=capsys)

    assert code == 0 and "0 folded, 0 refused" in out
    assert (tmp_path / "card.pjx").read_text() == folded


def test_pyblock_reminds_about_the_stubs_and_what_must_import_pyjinhx(tmp_path, capsys):
    make_card(tmp_path)

    _, out = run("pyblock", tmp_path, capsys=capsys)

    assert "something must import pyjinhx before this module" in out
    assert "python -m pyjinhx.stubgen" in out


def test_pyblock_asks_for_the_import_only_when_the_package_root_lacks_it(
    package, capsys
):
    write(package / "card.py", CARD_PY)
    write(package / "card.pjx", CARD_PJX)

    _, out = run("pyblock", package, capsys=capsys)
    assert f"{package / '__init__.py'} needs `import pyjinhx`" in out

    (package / "__init__.py").write_text("import pyjinhx\n")
    _, out = run("pyblock", package, capsys=capsys)
    assert "needs `import pyjinhx`" not in out and "something must import" not in out


def test_pyblock_drops_a_byte_order_mark_from_either_file(package, capsys):
    (package / "card.py").write_bytes(
        b"\xef\xbb\xbf" + textwrap.dedent(CARD_PY).lstrip("\n").encode()
    )
    (package / "card.pjx").write_bytes(b"\xef\xbb\xbf" + CARD_PJX.encode())

    code, _ = run("pyblock", package, "--write", capsys=capsys)

    assert code == 0
    assert "\ufeff" not in (package / "card.pjx").read_text(encoding="utf-8")


def test_pyblock_refuses_a_header_behind_a_byte_order_mark(tmp_path, capsys):
    make_card(tmp_path)
    (tmp_path / "card.pjx").write_bytes(b"\xef\xbb\xbf{#def title: str #}\n")
    refused(tmp_path, "already has a {#def#} header", capsys)


def test_pyblock_refuses_a_named_file_that_is_not_python_but_skips_it_in_a_walk(
    tmp_path, capsys
):
    broken = write(tmp_path / "card.py", "class Card(:\n")
    write(tmp_path / "card.pjx", CARD_PJX)

    code, out = run("pyblock", tmp_path, capsys=capsys)
    assert code == 0 and "0 refused" in out

    refused(tmp_path, "not valid Python", capsys, broken)


def test_pyblock_reports_references_in_hidden_files_but_not_hidden_directories(
    tmp_path, capsys
):
    components = tmp_path / "components"
    make_card(components)
    write(tmp_path / ".coveragerc", "omit = components/card.py\n")
    write(tmp_path / ".github" / "ci.yml", "run: python components/card.py\n")

    _, out = run("pyblock", components, "--root", tmp_path, capsys=capsys)

    assert ".coveragerc:1:" in out
    assert "ci.yml" not in out


def test_pyblock_notes_a_module_that_reads_its_own_file_or_main(tmp_path, capsys):
    write(
        tmp_path / "card.py",
        CARD_PY + "\n    HERE = __file__\n",
    )
    write(tmp_path / "card.pjx", CARD_PJX)

    code, out = run("pyblock", tmp_path, capsys=capsys)

    assert code == 0
    assert "__file__ becomes card.pjx" in out and "python card.py" in out


def test_pyblock_says_when_the_pjx_already_holds_this_module(tmp_path, capsys):
    make_card(tmp_path)
    folded = "{#python\n" + textwrap.dedent(CARD_PY).lstrip("\n") + "#}\n" + CARD_PJX
    (tmp_path / "card.pjx").write_text(folded)

    code, out = run("pyblock", tmp_path, capsys=capsys)

    assert code == 1
    assert "already folded; delete card.py" in out


def test_pyblock_writes_through_a_temporary_file_and_leaves_none_behind(
    tmp_path, capsys
):
    make_card(tmp_path)

    run("pyblock", tmp_path, "--write", capsys=capsys)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["card.pjx"]


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
