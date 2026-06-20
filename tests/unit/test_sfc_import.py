import sys
import textwrap

import pytest

from pyjinhx.importer import install


@pytest.fixture
def pjx_pkg(tmp_path, monkeypatch):
    """A tmp dir on sys.path holding .pjx components; cleans import state."""
    install()
    monkeypatch.syspath_prepend(str(tmp_path))
    pkg = tmp_path / "comps"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    # drop any cached test modules between runs (including the package itself)
    for name in [n for n in sys.modules if n == "comps" or n.startswith("comps.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    return pkg


def write(pkg, name, body):
    (pkg / f"{name}.pjx").write_text(textwrap.dedent(body))


def test_imports_class_from_pjx(pjx_pkg):
    write(pjx_pkg, "pjxcounter", """
        {# python
        from pyjinhx import BaseComponent

        class PjxCounter(BaseComponent):
            remaining: int
        #}
        <div>{{ remaining }} left</div>
    """)
    from comps.pjxcounter import PjxCounter
    assert PjxCounter(remaining=3).remaining == 3
    assert "3 left" in PjxCounter(remaining=3).render()


def test_template_bound_to_class(pjx_pkg):
    write(pjx_pkg, "card", """
        {# python
        from pyjinhx import BaseComponent

        class Card(BaseComponent):
            title: str
        #}
        <article>{{ title }}</article>
    """)
    from comps.card import Card
    assert Card._pjx_inline_template.strip() == "<article>{{ title }}</article>"
    assert Card._pjx_source_path.endswith("card.pjx")


def test_no_block_is_not_importable(pjx_pkg):
    write(pjx_pkg, "plain", "<div>{{ x }}</div>\n")
    with pytest.raises(ImportError, match="no .# python"):
        __import__("comps.plain")


def test_zero_component_classes_errors(pjx_pkg):
    write(pjx_pkg, "empty", "{# python\nx = 1\n#}\n<p></p>\n")
    with pytest.raises(ImportError, match="no component class"):
        __import__("comps.empty")


def test_multiple_component_classes_error(pjx_pkg):
    write(pjx_pkg, "two", """
        {# python
        from pyjinhx import BaseComponent
        class A(BaseComponent): ...
        class B(BaseComponent): ...
        #}
        <p></p>
    """)
    with pytest.raises(ImportError, match="exactly one component class"):
        __import__("comps.two")


def test_helper_non_component_class_is_allowed(pjx_pkg):
    write(pjx_pkg, "helped", """
        {# python
        from dataclasses import dataclass
        from pyjinhx import BaseComponent

        @dataclass
        class Helper:
            value: str = "hi"

        class Helped(BaseComponent):
            title: str = Helper().value
        #}
        <p>{{ title }}</p>
    """)
    from comps.helped import Helped
    assert Helped._pjx_inline_template.strip() == "<p>{{ title }}</p>"
    assert "hi" in Helped().render()


def test_py_and_pjx_shadow_errors(pjx_pkg):
    write(pjx_pkg, "dup", "{# python\nfrom pyjinhx import BaseComponent\nclass Dup(BaseComponent): ...\n#}\n<p></p>\n")
    (pjx_pkg / "dup.py").write_text("Dup = 1\n")
    with pytest.raises(ImportError, match="both .* and .*\\.pjx"):
        __import__("comps.dup")


def test_reactive_sfc_round_trips(pjx_pkg):
    write(pjx_pkg, "rcounter", """
        {# python
        from pyjinhx import ReactiveComponent, MutationKey

        class Keys(MutationKey):
            TODOS = "todos"

        class RCounter(ReactiveComponent, react={Keys.TODOS}):
            remaining: int

            @classmethod
            def load(cls) -> "RCounter":
                return cls(remaining=7)
        #}
        <div>{{ remaining }} left</div>
    """)
    from comps.rcounter import RCounter
    inst = RCounter.load()
    assert inst.remaining == 7
    html = inst.render()
    assert "7 left" in html
    assert "data-pjx-type" in html  # reactive stamping unchanged
