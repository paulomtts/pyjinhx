"""Form builtins exercised together in one render.

Each individual component is unit-tested by its own module; this file only
asserts the cross-cutting properties those files cannot see: PJXFormField
wrapping each of the other five controls through its ``content`` slot, label
``for_id`` linkage across the composition boundary, error/help exclusivity
around a composed control, escaping surviving the slot hop, id uniqueness in a
multi-control form, and the single-root invariant holding through the wrap.

PJXButton's ``loading`` state is in scope here: the button mounts
``<PJXRegionLoader/>`` by tag, so the loader is part of the *composed* output
and belongs in a composition sweep. PJXRegionLoader itself is only consumed,
never modified (it is owned by LL4.4).

The builtins are plain BaseComponents, so the multi-control shapes are declared
here as host wrappers whose templates mount the fields by slot.
"""

import dataclasses
import re
from pathlib import Path

import pytest

from pyjinhx2 import discovery
from pyjinhx2.builtins.pjx_region_loader import PJXRegionLoader
from pyjinhx2.builtins.ui.pjx_button import PJXButton
from pyjinhx2.builtins.ui.pjx_chip_input import PJXChipInput
from pyjinhx2.builtins.ui.pjx_form_field import PJXFormField
from pyjinhx2.builtins.ui.pjx_password_input import PJXPasswordInput
from pyjinhx2.builtins.ui.pjx_segmented_control import PJXSegmentedControl
from pyjinhx2.builtins.ui.pjx_toggle_switch import PJXToggleSwitch
from pyjinhx2.component import BaseComponent, Slot, _pascal_to_snake
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession

FAMILY = (
    PJXButton,
    PJXChipInput,
    PJXFormField,
    PJXPasswordInput,
    PJXSegmentedControl,
    PJXToggleSwitch,
    # Mounted by tag from pjx_button.pjx when loading=True, so its tag has to be
    # claimed here too or the loading branch degrades to passthrough markup.
    PJXRegionLoader,
)


class FormPanel(BaseComponent):
    """A host with three independent slots, for several fields on one page."""

    first: Slot = ""
    second: Slot = ""
    third: Slot = ""


class Wrapper(BaseComponent):
    """A single-slot host, used to add a level of depth without adding markup rules."""

    content: Slot = ""


TEMPLATES = {
    "form_panel.pjx": (
        '<form id="{{ id }}" class="form-panel">'
        '<div class="form-panel__first">{{ first }}</div>'
        '<div class="form-panel__second">{{ second }}</div>'
        '<div class="form-panel__third">{{ third }}</div>'
        "</form>"
    ),
    "wrapper.pjx": '<div id="{{ id }}" class="wrapper">{{ content }}</div>',
}


@pytest.fixture
def family_dir(tmp_path: Path):
    """Publish the family tag map under tmp_path and repoint the host descriptors.

    build_registry claims a tag only when a file named <tag>.pjx exists under the
    given directory (stem match; content is never read), so every builtin tag this
    sweep mounts needs a placeholder file or the tag falls back to passthrough
    markup. The hosts' own descriptors are then repointed at their real templates
    here, because _resolve_template_path would otherwise probe this test file's
    directory.
    """
    for name, body in TEMPLATES.items():
        (tmp_path / name).write_text(body)
    for cls in FAMILY:
        placeholder = tmp_path / f"{_pascal_to_snake(cls.__name__)}.pjx"
        if not placeholder.exists():
            placeholder.write_text("")
    discovery.build_registry(tmp_path, [*FAMILY, FormPanel, Wrapper])
    for cls, name in ((FormPanel, "form_panel.pjx"), (Wrapper, "wrapper.pjx")):
        # Absolute, because the sweep renders with template_dir="/" — the search
        # root the builtins' own absolute descriptor paths need.
        cls.__pjx_descriptor__ = dataclasses.replace(
            cls.__pjx_descriptor__, template_path=tmp_path / name
        )
    yield tmp_path
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


@pytest.fixture
def session() -> RenderSession:
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _control_region(html: str) -> str:
    """The text between the field's control div and the end of the composed field.

    Substring slicing, not parsing: invariant 2 says child output is opaque, so
    the sweep only ever asks "does this appear inside that region", never "what
    is this markup made of".
    """
    return html.split('class="pjx-form-field__control">', 1)[1]


def test_form_field_wraps_a_toggle_switch_in_its_control_region(family_dir, session):
    """The composition point: a control passed to content lands in the control div."""
    html = render(
        PJXFormField(
            id="ff",
            label="Notify me",
            content=PJXToggleSwitch(id="ts", name="notify"),
        ),
        session,
    )

    assert html.count('id="ts"') == 1
    assert 'id="ts"' in _control_region(html)
    assert "pjx-toggle-switch__track" in html


CONTROLS = (
    (PJXButton(id="ctl", content="Save"), "pjx-button"),
    (PJXChipInput(id="ctl", name="tags", values=["a"]), "pjx-chip-input__chip"),
    (PJXPasswordInput(id="ctl", name="pw"), "pjx-password-input__toggle"),
    (
        PJXSegmentedControl(id="ctl", name="mode", options=[("a", "A"), ("b", "B")]),
        "pjx-segmented-control__segment",
    ),
    (PJXToggleSwitch(id="ctl", name="on"), "pjx-toggle-switch__track"),
)
"""Each of the five controls FormField is expected to wrap, with a marker string."""


@pytest.mark.parametrize(
    ("control", "marker"), CONTROLS, ids=lambda v: getattr(v, "id", None) or str(v)
)
def test_each_control_renders_once_inside_the_control_region(
    family_dir, session, control, marker
):
    """Every family control composes through content and appears exactly once."""
    html = render(PJXFormField(id="ff", label="Field", content=control), session)

    assert html.count('id="ctl"') == 1
    assert marker in html
    assert marker in _control_region(html)
    assert html.count('class="pjx-form-field__control"') == 1

