"""Tests for fold_components declass: turning a component class into a template header."""

import textwrap
from pathlib import Path

import pytest

from pyjinhx.rendering.pipeline import render
from pyjinhx.rendering.session import RenderSession
from tests.scripts.fold_components._helpers import render_class, run, write

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
