"""PJXAccordion renders the single-root <details> shell of the accordion family (port of v0.x pyjinhx/builtins/ui/pjx_accordion)."""

import dataclasses

import pytest

from pyjinhx2.builtins.ui.pjx_accordion import PJXAccordion
from pyjinhx2.component import BaseComponent, Slot
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def accordion_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXAccordion(id="a", **kw), session)


def test_default_render_is_a_single_open_details(accordion_session):
    assert (
        _html(accordion_session)
        == '<details id="a" class="pjx-accordion" open></details>'
    )


def test_open_false_omits_the_open_attribute(accordion_session):
    assert _html(accordion_session, open=False) == (
        '<details id="a" class="pjx-accordion"></details>'
    )


def test_group_renders_the_name_attribute(accordion_session):
    assert 'name="g"' in _html(accordion_session, group="g")


def test_group_default_omits_the_name_attribute(accordion_session):
    assert "name=" not in _html(accordion_session)


def test_class_name_appended_to_root(accordion_session):
    assert 'class="pjx-accordion mine"' in _html(accordion_session, class_name="mine")


def test_empty_class_name_adds_nothing(accordion_session):
    assert 'class="pjx-accordion"' in _html(accordion_session, class_name="")


def test_string_content_renders_escaped_inside_root(accordion_session):
    """v2 narrowing of v0.x: a plain str in a Slot is escaped; only components emit markup."""
    html = _html(accordion_session, content="<p>raw</p>")
    assert html.count("<details") == 1
    assert "&lt;p&gt;raw&lt;/p&gt;" in html
    assert "<p>raw</p>" not in html


class AccordionChild(BaseComponent):
    """A minimal component child, to prove a nested component renders inside <details>."""

    content: Slot = ""


@pytest.fixture
def accordion_child_template(tmp_path):
    """Give AccordionChild a real template on disk and repoint its descriptor at it.

    A class defined ad hoc in a test module resolves a template candidate
    co-located with the test file, which does not exist.
    """
    path = tmp_path / "accordion_child.pjx"
    path.write_text('<span id="{{ id }}" class="child">{{ content }}</span>')
    AccordionChild.__pjx_descriptor__ = dataclasses.replace(
        AccordionChild.__pjx_descriptor__, template_path=path
    )
    yield path


def test_component_content_renders_inside_details(
    accordion_session, accordion_child_template
):
    html = _html(accordion_session, content=AccordionChild(id="c", content="hi"))
    assert html.count("<details") == 1
    assert '<span id="c" class="child">hi</span>' in html


def test_assets_are_discovered_from_the_component_directory():
    """CSS sits next to the module and is picked up by the descriptor, with no manual wiring."""
    descriptor = PJXAccordion.__pjx_descriptor__
    assert descriptor.css_paths
    assert any(p.name == "pjx_accordion.css" for p in descriptor.css_paths)
