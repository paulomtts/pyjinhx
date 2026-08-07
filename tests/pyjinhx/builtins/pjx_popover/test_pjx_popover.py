"""PJXPopover renders the positioned root shell that anchors a trigger and its panel (port of v0.x pyjinhx/builtins/ui/pjx_popover/pjx_popover.py)."""

import dataclasses

import pytest
from pydantic import ValidationError

from pyjinhx._component import BaseComponent, Slot
from pyjinhx.builtins.ui.pjx_popover import PJXPopover
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def popover_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXPopover(id="p", **kw), session)


def test_default_render_is_a_single_start_aligned_root(popover_session):
    assert _html(popover_session) == (
        '<div id="p" class="pjx-popover" data-pjx-popover></div>'
    )


def test_align_start_matches_the_default(popover_session):
    assert _html(popover_session, align="start") == _html(popover_session)


def test_align_end_adds_the_alignment_modifier(popover_session):
    assert 'class="pjx-popover pjx-popover--align-end"' in _html(
        popover_session, align="end"
    )


def test_class_name_appended_to_root(popover_session):
    assert 'class="pjx-popover mine"' in _html(popover_session, class_name="mine")


def test_string_content_is_interpolated(popover_session):
    assert ">hello</div>" in _html(popover_session, content="hello")


class PopoverChild(BaseComponent):
    """A minimal component child, to prove a nested component renders inside the root."""

    content: Slot = ""


@pytest.fixture
def popover_child_template(tmp_path):
    """Give PopoverChild a real template on disk and repoint its descriptor at it."""
    path = tmp_path / "popover_child.pjx"
    path.write_text('<span id="{{ id }}" class="child">{{ content }}</span>')
    PopoverChild.__pjx_descriptor__ = dataclasses.replace(
        PopoverChild.__pjx_descriptor__, template_path=path
    )
    yield path


def test_component_content_renders_inside_the_root(
    popover_session, popover_child_template
):
    html = _html(popover_session, content=PopoverChild(id="c", content="Inner"))
    assert '<span id="c" class="child">Inner</span>' in html


def test_invalid_align_is_rejected():
    with pytest.raises(ValidationError):
        PJXPopover(id="p", align="middle")  # type: ignore[arg-type]


def test_dropped_behavior_field_is_rejected():
    """`behavior` did not survive the v2 port; extra="forbid" turns it into an error."""
    with pytest.raises(ValidationError):
        PJXPopover(id="p", behavior=True)  # type: ignore[call-arg]


def test_extra_attrs_surface_on_the_root(popover_session):
    html = _html(popover_session, extra_attrs={"data-testid": "popover"})
    assert 'data-testid="popover"' in html[: html.index(">")]


def test_assets_are_discovered_from_the_component_directory():
    """CSS and JS sit next to the module and are picked up by the descriptor, with no manual wiring."""
    descriptor = PJXPopover.__pjx_descriptor__
    assert any(p.name == "pjx_popover.js" for p in descriptor.js_paths)
    assert any(p.name == "pjx_popover.css" for p in descriptor.css_paths)
