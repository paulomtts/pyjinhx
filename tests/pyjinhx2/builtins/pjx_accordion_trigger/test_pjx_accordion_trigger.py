"""PJXAccordionTrigger renders the <summary> row with its chevron icon (port of v0.x pyjinhx/builtins/ui/pjx_accordion_trigger)."""

import dataclasses

import pytest

from pyjinhx2 import discovery
from pyjinhx2.builtins.ui.pjx_accordion_trigger import PJXAccordionTrigger
from pyjinhx2.builtins.ui.pjx_icon import PJXIcon
from pyjinhx2.component import BaseComponent, Slot
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def trigger_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


@pytest.fixture
def icon_registered():
    """Publish the ``pjx_icon`` tag for this test only.

    ``<PJXIcon/>`` in the trigger template is resolved at render time through
    discovery's tag map, not through a Python import; an unclaimed tag is
    emitted verbatim instead. The map is process-global, so it is snapshotted
    and restored.
    """
    before = discovery._registry.mapping
    discovery.register_class("pjx_icon", PJXIcon)
    yield
    discovery._registry.mapping = before


def _html(session, **kw) -> str:
    return render(PJXAccordionTrigger(id="t", **kw), session)


def test_default_render_is_a_single_summary(trigger_session, icon_registered):
    html = _html(trigger_session)
    assert html.count("<summary") == 1
    assert html.startswith('<summary id="t" class="pjx-accordion__trigger">')
    assert html.endswith("</summary>")


def test_chevron_icon_tag_expands_to_svg_markup(trigger_session, icon_registered):
    html = _html(trigger_session)
    assert "<PJXIcon" not in html
    assert "<svg" in html
    assert 'class="pjx-icon pjx-accordion__chevron"' in html


def test_disabled_emits_aria_disabled(trigger_session, icon_registered):
    html = _html(trigger_session, disabled=True)
    assert 'aria-disabled="true"' in html
    assert 'tabindex="-1"' in html


def test_disabled_default_omits_aria_disabled(trigger_session, icon_registered):
    assert "aria-disabled" not in _html(trigger_session, disabled=False)


def test_class_name_appended_to_root(trigger_session, icon_registered):
    assert 'class="pjx-accordion__trigger mine"' in _html(
        trigger_session, class_name="mine"
    )


def test_empty_class_name_adds_nothing(trigger_session, icon_registered):
    assert 'class="pjx-accordion__trigger"' in _html(trigger_session, class_name="")


class TriggerChild(BaseComponent):
    """A minimal component child, to prove a nested component renders inside the summary."""

    content: Slot = ""


@pytest.fixture
def trigger_child_template(tmp_path):
    """Give TriggerChild a real template on disk and repoint its descriptor at it."""
    path = tmp_path / "trigger_child.pjx"
    path.write_text('<span id="{{ id }}" class="child">{{ content }}</span>')
    TriggerChild.__pjx_descriptor__ = dataclasses.replace(
        TriggerChild.__pjx_descriptor__, template_path=path
    )
    yield path


def test_component_content_renders_after_the_icon(
    trigger_session, icon_registered, trigger_child_template
):
    html = _html(trigger_session, content=TriggerChild(id="l", content="Label"))
    assert html.index("pjx-accordion__chevron") < html.index('id="l"')
    assert "Label" in html


def test_assets_are_discovered_from_the_component_directory():
    """JS sits next to the module and is picked up by the descriptor, with no manual wiring."""
    descriptor = PJXAccordionTrigger.__pjx_descriptor__
    assert descriptor.js_paths
    assert any(p.name == "pjx_accordion_trigger.js" for p in descriptor.js_paths)
