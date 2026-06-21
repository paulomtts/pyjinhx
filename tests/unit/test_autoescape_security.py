import pytest

from pyjinhx import Renderer


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def test_scalar_attribute_value_is_escaped():
    from pyjinhx.builtins import PJXAvatar
    html = str(PJXAvatar(id="a", initials="x", alt='" onmouseover="alert(1)').render())
    assert 'onmouseover="alert(1)"' not in html
    assert "&#34;" in html or "&quot;" in html


def test_scalar_text_value_is_escaped():
    from pyjinhx.builtins import PJXCardHeader
    html = str(PJXCardHeader(id="c", title="<script>alert(1)</script>").render())
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_loop_derived_value_is_escaped():
    from pyjinhx.builtins import PJXBreadcrumb
    html = str(PJXBreadcrumb(id="b", items=[("<script>x</script>", "/")]).render())
    assert "<script>x</script>" not in html


def test_slot_string_renders_raw():
    from pyjinhx.builtins import PJXCardBody
    html = str(PJXCardBody(id="c", content="<p data-x='1'>hi</p>").render())
    assert "<p data-x='1'>hi</p>" in html  # slot HTML NOT escaped


def test_nested_component_renders_raw():
    from pyjinhx.builtins import PJXCardBody, PJXBadge
    html = str(PJXCardBody(id="c", content=PJXBadge(id="b", label="New")).render())
    assert "pjx-badge" in html and "&lt;span" not in html


def test_collection_slot_text_key_is_escaped():
    from pyjinhx.builtins import PJXTabGroup
    html = str(PJXTabGroup(id="t", tabs={"<script>alert(1)</script>": "<b>panel</b>"}).render())
    assert "<script>alert(1)</script>" not in html      # label (dict key) escaped
    assert "&lt;script&gt;" in html
    assert "<b>panel</b>" in html                          # panel (dict value) raw


def test_markup_value_on_scalar_field_is_still_escaped():
    """Pydantic coerces markupsafe.Markup to plain str on str-typed fields,
    so the safe marker is lost before the context builder runs.  Markup is NOT
    a working escape hatch for scalar fields; use Slot or |safe instead."""
    from markupsafe import Markup
    from pyjinhx.builtins import PJXCardHeader
    html = str(PJXCardHeader(id="c", title=Markup("<b>x</b>")).render())
    assert "<b>x</b>" not in html   # still escaped — Markup hatch does NOT work here
    assert "&lt;b&gt;" in html


def test_button_start_end_slot_render_raw():
    from pyjinhx.builtins import PJXButton
    html = str(PJXButton(id="b", start="<svg data-x='1'>i</svg>", center="Save").render())
    assert "<svg data-x='1'>i</svg>" in html  # start is Slot → raw
    assert "Save" in html


def test_button_center_label_is_escaped():
    from pyjinhx.builtins import PJXButton
    html = str(PJXButton(id="b2", center="<b>x</b>").render())
    assert "<b>x</b>" not in html   # center is text (str) → escaped; use start/end for icons
    assert "&lt;b&gt;" in html


def test_dropdown_trigger_slot_renders_raw():
    from pyjinhx.builtins import PJXDropdown
    html = str(PJXDropdown(id="d", trigger="<b>menu</b>", items=[]).render())
    assert "<b>menu</b>" in html  # trigger is Slot → raw


def test_modal_close_content_slot_renders_raw():
    from pyjinhx.builtins import PJXModal
    html = str(PJXModal(id="m", body="x", close_content="<i class='x'></i>").render())
    assert "<i class='x'></i>" in html  # close_content is Slot → raw


def test_tooltip_trigger_slot_renders_raw():
    from pyjinhx.builtins import PJXTooltip
    html = str(PJXTooltip(id="t", trigger="<b>hover</b>", tip="hint").render())
    assert "<b>hover</b>" in html  # trigger is Slot → raw


def test_drawer_close_content_slot_renders_raw():
    from pyjinhx.builtins import PJXDrawer
    html = str(PJXDrawer(id="dr", close_content="<i class='close'></i>").render())
    assert "<i class='close'></i>" in html  # close_content is Slot → raw


# --- Nested-tag components (#120): escaping must survive tag expansion ---

def test_nested_tag_component_scalar_text_is_escaped():
    """PJXAccordion embeds <PJXIcon/>; entities must not be decoded by tag expansion."""
    from pyjinhx.builtins import PJXAccordion
    html = str(
        PJXAccordion(id="a", label="<script>alert(1)</script>", content="ok").render()
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_nested_tag_component_slot_renders_raw():
    from pyjinhx.builtins import PJXAccordion
    html = str(
        PJXAccordion(id="a2", label="t", content="<p data-x='1'>hi</p>").render()
    )
    assert "<p data-x='1'>hi</p>" in html  # content slot stays raw


def test_nested_tag_component_scalar_is_escaped_when_nested_tag_present():
    """PJXButton loading state embeds <PJXRegionLoader/>; the center scalar must still
    escape even though a nested PascalCase tag triggers tag expansion."""
    from pyjinhx.builtins import PJXButton
    html = str(
        PJXButton(id="b", center="<b>x</b>", loading=True).render()
    )
    assert "<b>x</b>" not in html  # center is text (str) → escaped through tag expansion
    assert "&lt;b&gt;" in html


def test_nested_tag_component_still_renders_nested_component():
    """The accordion's <PJXIcon/> chevron must still render after the parser change."""
    from pyjinhx.builtins import PJXAccordion
    html = str(PJXAccordion(id="a3", label="t", content="ok").render())
    assert "pjx-icon" in html or "<svg" in html


# --- #120 regression: bare `&word` text must not gain a spurious `;` ---

def test_bare_ampersand_in_slot_text_not_corrupted():
    """`R&D`/`Q&A` in slot text must not become `R&D;`/`Q&A;` during tag expansion."""
    from pyjinhx.builtins import PJXAccordion
    html = str(
        PJXAccordion(id="r", label="t", content="<p>R&D and Q&A</p>").render()
    )
    assert "R&D;" not in html
    assert "Q&A;" not in html


def test_bare_ampersand_in_slot_attribute_not_corrupted():
    """`href='?x=1&y=2'` must not become `?x=1&y;=2` during tag expansion."""
    from pyjinhx.builtins import PJXAccordion
    html = str(
        PJXAccordion(id="r2", label="t", content="<a href='?x=1&y=2'>L</a>").render()
    )
    assert "&y;=2" not in html
    assert "?x=1&y=2" in html or "?x=1&amp;y=2" in html
