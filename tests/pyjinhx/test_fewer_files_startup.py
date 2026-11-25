"""What each shape costs at startup, for a few hundred components.

Records rather than asserts: import, registry build and the first render of a
page using every component, per shape, printed so a regression is visible
in the test output. Timings on a shared machine are too noisy to gate on.
"""

import importlib
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from pyjinhx import BaseComponent, Slot, discovery
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession, accumulate_assets, request_scope

COUNT = 300

TEMPLATE = """<article class="widget-{n}">
  <h3>{{{{ label }}}}</h3>
  <p>{{{{ count }}}} items</p>
</article>"""

CSS = ".widget-{n} {{ padding: {n}px; }}"


class Host(BaseComponent):
    markup: Slot = ""

    template = "<main>{{ markup }}</main>"


def class_source(n: int, inline: bool) -> str:
    body = f"class Widget{n}(BaseComponent):\n    label: str\n    count: int = 0\n"
    if not inline:
        return body
    document = f"{TEMPLATE.format(n=n)}\n{{#css\n{CSS.format(n=n)}\n#}}"
    indented = "".join(f"        {line}\n" for line in document.splitlines())
    return f'{body}\n    template = r"""\n{indented}    """\n'


def write_split(root: Path) -> None:
    for n in range(COUNT):
        folder = root / f"widget{n}"
        folder.mkdir(parents=True)
        (folder / f"widget{n}.py").write_text(
            "from pyjinhx import BaseComponent\n\n\n" + class_source(n, inline=False)
        )
        (folder / f"widget{n}.pjx").write_text(TEMPLATE.format(n=n) + "\n")
        (folder / f"widget{n}.css").write_text(CSS.format(n=n) + "\n")


def write_template_only(root: Path) -> None:
    for n in range(COUNT):
        folder = root / f"widget{n}"
        folder.mkdir(parents=True)
        (folder / f"widget{n}.pjx").write_text(
            "{#def label: str, count: int = 0 #}\n"
            f"{TEMPLATE.format(n=n)}\n{{#css\n{CSS.format(n=n)}\n#}}\n"
        )


def single_file_writer(per_module: int) -> Callable[[Path], None]:
    def write(root: Path) -> None:
        root.mkdir(parents=True)
        for first in range(0, COUNT, per_module):
            classes = [
                class_source(n, inline=True)
                for n in range(first, min(first + per_module, COUNT))
            ]
            (root / f"widgets{first}.py").write_text(
                "from pyjinhx import BaseComponent\n\n\n" + "\n\n".join(classes)
            )

    return write


LAYOUTS: dict[str, Callable[[Path], None]] = {
    "S": write_split,
    "T": write_template_only,
    "C, 1 per module": single_file_writer(1),
    "C, 10 per module": single_file_writer(10),
    "C, 300 in one module": single_file_writer(COUNT),
}


@pytest.fixture
def importable(tmp_path: Path) -> Iterator[Path]:
    """``tmp_path`` on ``sys.path``, with whatever was imported from it dropped after."""
    sys.path.insert(0, str(tmp_path))
    yield tmp_path
    sys.path.remove(str(tmp_path))
    for name in [n for n in sys.modules if n.startswith("startup_")]:
        del sys.modules[name]
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def start(root: Path, package: str) -> float:
    """Seconds to import ``root``'s modules, build the registry and render once."""
    began = time.perf_counter()
    importlib.invalidate_caches()
    classes: list[type] = []
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).with_suffix("").parts
        module = importlib.import_module(".".join([package, *parts]))
        classes.extend(
            value
            for value in vars(module).values()
            if isinstance(value, type)
            and issubclass(value, BaseComponent)
            and value.__module__ == module.__name__
        )
    discovery.build_registry(root, [*classes, Host])
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    markup = "".join(f'<Widget{n} label="w{n}" count="{n}"/>' for n in range(COUNT))
    with request_scope(session=session):
        html = render(Host(markup=markup), session)
    elapsed = time.perf_counter() - began
    assert html.count("<article") == COUNT
    assert "<Widget" not in html
    return elapsed


def test_record_startup_cost_per_shape(importable: Path, capsys: pytest.CaptureFixture):
    timings: dict[str, float] = {}
    for index, (layout, write) in enumerate(LAYOUTS.items()):
        package = f"startup_{index}"
        write(importable / package)
        timings[layout] = start(importable / package, package)
    baseline = timings["S"]
    with capsys.disabled():
        print(f"\nstartup for {COUNT} components (import + registry + first render):")
        for layout, seconds in timings.items():
            print(
                f"  {layout:<22} {seconds * 1000:7.1f} ms  {seconds / baseline:4.1f}x S"
            )
