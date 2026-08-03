"""PJXIcon renders a themeable inline SVG from the vendored set (port of v0.x tests/unit/test_icon.py)."""

import dataclasses
import logging

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.component import BaseComponent
from pyjinhx.render import render
from pyjinhx.session import RenderSession


@pytest.fixture
def icon_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is an absolute Path computed at class
    definition time, but RenderSession builds FileSystemLoader(template_dir)
    and render() feeds it that absolute path straight through. Jinja only
    resolves an absolute path when the loader root is "/". Engine gap, not
    Icon's — see the blocking questions in the #500 plan.
    """
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXIcon(id="i", **kw), session)


def test_renders_single_root_svg_with_currentcolor(icon_session):
    html = _html(icon_session, name="plus")
    assert html.count("<svg") == 1
    assert 'stroke="currentColor"' in html
    assert 'fill="none"' in html
    assert '<path d="M5 12h14"' in html  # plus inner markup, unescaped


def test_int_size_renders_pixels(icon_session):
    html = _html(icon_session, name="plus", size=20)
    assert 'width="20px"' in html
    assert 'height="20px"' in html


def test_str_size_renders_verbatim(icon_session):
    html = _html(icon_session, name="plus", size="1.5rem")
    assert 'width="1.5rem"' in html


def test_label_sets_role_and_title(icon_session):
    html = _html(icon_session, name="search", label="Buscar")
    assert 'role="img"' in html
    assert "<title>Buscar</title>" in html
    assert "aria-hidden" not in html


def test_no_label_is_aria_hidden(icon_session):
    html = _html(icon_session, name="search")
    assert 'aria-hidden="true"' in html
    assert "<title>" not in html


def test_unknown_name_renders_hidden_span_and_warns(icon_session, caplog):
    with caplog.at_level(logging.WARNING):
        html = _html(icon_session, name="definitely-not-an-icon")
    assert "<svg" not in html
    assert "<span" in html
    assert " hidden" in html
    assert any("definitely-not-an-icon" in r.message for r in caplog.records)


def test_class_name_renders_on_root(icon_session):
    html = _html(icon_session, name="plus", class_name="mine")
    assert 'class="pjx-icon mine"' in html


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's arbitrary data-* pass-through is gone.

    Deliberate narrowing of v0.x behavior — see the #500 plan's blocking questions.
    """
    with pytest.raises(ValidationError):
        PJXIcon(id="i", name="plus", **{"data-x": "y"})  # pyright: ignore[reportCallIssue, reportArgumentType]


def test_multi_root_template_still_raises(icon_session, tmp_path):
    """Invariant 3 regression guard: two roots must raise, no try/except concession."""
    module_dir = tmp_path / "pkg"
    module_dir.mkdir()
    template_path = module_dir / "two_roots.pjx"
    template_path.write_text("<span></span><span></span>")

    class TwoRoots(BaseComponent):
        pass

    TwoRoots.__pjx_descriptor__ = dataclasses.replace(
        PJXIcon.__pjx_descriptor__,
        template_path=template_path,
        provenance={"template": TwoRoots},
    )

    with pytest.raises(ValueError):
        render(TwoRoots(id="t"), icon_session)
