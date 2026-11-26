"""Component sources, grammar loader and entry accessors for the manifest tests."""

import json
import sys
from importlib import resources
from pathlib import Path

from pyjinhx import manifest


def _grammar() -> dict:
    text = resources.files("pyjinhx").joinpath("block_grammar.json").read_text("utf-8")
    return json.loads(text)


BADGE = """\
{#def label: str, when: datetime.datetime,
      tone: Literal["info", "warn"] = "info", size: nowhere.mod.Size = nowhere.mod.DEFAULT #}
<span>{{ label }}</span>
"""


TODO_COUNT = """\
{#python
from pyjinhx import ReactiveComponent, Slot, Children


class TodoCount(ReactiveComponent):
    remaining: int = 0
    mode: Literal["a", "b"] = "a"
    title: Slot | None = None
    items: list[Slot]
    body: Children
    label: str = ...
    _private: int = 0

    @property
    def done(self) -> bool:
        return not self.remaining

    def describe(self):
        return "x"

    @classmethod
    def load(cls):
        return cls()
#}
<div>{{ remaining }}</div>
{#css
.count { color: red; }
#}
"""


CHIP = '''\
from pyjinhx import BaseComponent


class Chip(BaseComponent):
    label: str

    template = """
    <b>{{ label }}</b>
    """


class Tag(BaseComponent):
    template = "<i></i>"


class Helper:
    pass
'''


CARD_PY = """\
from pyjinhx import BaseComponent


class Card(BaseComponent):
    title: str
"""


def _write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _abs(relative: str) -> str:
    """The absolute POSIX path of ``relative`` under the working directory."""
    return (Path.cwd() / relative).as_posix()


def _at(entry: dict) -> tuple[int, int]:
    """The line and column where an entry's range starts."""
    start = entry["range"]["start"]
    return start["line"], start["column"]


def _components(tree) -> dict[str, dict]:
    result = manifest.describe([Path("app")])
    return {c["tag"]: c for c in result["components"] if not c["builtin"]}


def _one(diagnostics: list[dict], code: str) -> dict:
    found = [d for d in diagnostics if d["code"] == code]
    assert len(found) == 1, diagnostics
    return found[0]


def _document(tree, text: str, name: str = "card.pjx") -> list[dict]:
    (tree / name).write_text(text, encoding="utf-8")
    return manifest.describe([Path(name)])["diagnostics"]


GOOD = "{#python\nclass Card:\n    title: str\n#}\n<p>{{ title }}</p>\n"


def _stdin(monkeypatch, text: str) -> None:
    import io

    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(text.encode())))
