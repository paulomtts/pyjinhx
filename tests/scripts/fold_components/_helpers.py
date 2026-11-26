"""The loaded fold_components script and the write/run/render helpers for its tests."""

import importlib
import importlib.util
import re
import sys
import textwrap
from pathlib import Path

import pytest

from pyjinhx.rendering.pipeline import render
from pyjinhx.rendering.session import RenderSession, accumulate_assets

SCRIPT = Path(__file__).parents[3] / "scripts" / "fold_components.py"


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


def refused(tmp_path: Path, reason: str, capsys, *paths: Path) -> None:
    before = {p: p.read_text() for p in tmp_path.rglob("*") if p.is_file()}
    code, out = run("pyblock", *(paths or (tmp_path,)), "--write", capsys=capsys)
    assert code == 1
    assert "refused" in out and reason in out
    assert {p: p.read_text() for p in tmp_path.rglob("*") if p.is_file()} == before
