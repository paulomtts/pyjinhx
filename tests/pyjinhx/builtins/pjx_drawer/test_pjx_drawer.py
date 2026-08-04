"""PJXDrawer renders the single-root <dialog> shell that composes the drawer parts (port of v0.x pyjinhx/builtins/ui/pjx_drawer)."""

import dataclasses

import pytest
from pydantic import ValidationError

from pyjinhx._component import BaseComponent, Slot
from pyjinhx.builtins.ui.pjx_drawer import PJXDrawer
from pyjinhx.builtins.ui.pjx_drawer_body import PJXDrawerBody
from pyjinhx.builtins.ui.pjx_drawer_footer import PJXDrawerFooter
from pyjinhx.builtins.ui.pjx_drawer_header import PJXDrawerHeader
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def drawer_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXDrawer(id="d", **kw), session)


def test_default_render_is_single_right_dialog_with_box(drawer_session):
    html = _html(drawer_session)
    assert html == (
        '<dialog class="pjx-drawer pjx-drawer--right" id="d">'
        '<div class="pjx-drawer__box"></div></dialog>'
    )


def test_id_renders_on_the_dialog(drawer_session):
    assert '<dialog class="pjx-drawer pjx-drawer--right" id="d"' in _html(
        drawer_session
    )


def test_side_left_modifier(drawer_session):
    assert 'class="pjx-drawer pjx-drawer--left"' in _html(drawer_session, side="left")


def test_side_bottom_modifier(drawer_session):
    assert 'class="pjx-drawer pjx-drawer--bottom"' in _html(
        drawer_session, side="bottom"
    )


def test_invalid_side_is_rejected():
    with pytest.raises(ValidationError):
        PJXDrawer(id="d", side="top")  # pyright: ignore[reportArgumentType]


def test_class_name_appended_after_the_side_modifier(drawer_session):
    assert 'class="pjx-drawer pjx-drawer--right wide"' in _html(
        drawer_session, class_name="wide"
    )


def test_empty_class_name_adds_nothing(drawer_session):
    assert 'class="pjx-drawer pjx-drawer--right"' in _html(
        drawer_session, class_name=""
    )


def test_open_on_mount_emits_data_attribute(drawer_session):
    assert "data-pjx-open-on-mount" in _html(drawer_session, open_on_mount=True)


def test_open_on_mount_default_omits_data_attribute(drawer_session):
    assert "data-pjx-open-on-mount" not in _html(drawer_session, open_on_mount=False)


def test_remove_on_close_emits_data_attribute(drawer_session):
    assert "data-pjx-remove-on-close" in _html(drawer_session, remove_on_close=True)


def test_remove_on_close_default_omits_data_attribute(drawer_session):
    assert "data-pjx-remove-on-close" not in _html(
        drawer_session, remove_on_close=False
    )


def test_lifecycle_attrs_and_class_name_combine(drawer_session):
    """v0.x contract case: a wide, self-opening, self-removing drawer."""
    html = _html(
        drawer_session, class_name="wide", open_on_mount=True, remove_on_close=True
    )
    assert 'class="pjx-drawer pjx-drawer--right wide"' in html
    assert "data-pjx-open-on-mount" in html
    assert "data-pjx-remove-on-close" in html


def test_no_inline_onclick_handler(drawer_session):
    """Dismissal is delegated in pjx_drawer.js; the markup carries no handlers."""
    assert "onclick" not in _html(drawer_session, open_on_mount=True)


def test_component_content_renders_inside_the_box(drawer_session):
    html = _html(drawer_session, content=PJXDrawerBody(id="b", content="Links here"))
    assert html.count("<dialog") == 1
    assert html.index("pjx-drawer__box") < html.index("pjx-drawer__body")
    assert "Links here" in html


def test_string_content_renders_raw_inside_root(drawer_session):
    """ADR 0003: a plain str in a Slot is authored markup, not escaped."""
    html = _html(drawer_session, content="<p>raw</p>")
    assert html.count("<dialog") == 1
    assert "<p>raw</p>" in html


def test_clean_break_removed_fields():
    """v0.x already dropped these from the shell (they live on the parts); v2 must not reintroduce them."""
    for gone in (
        "title",
        "header",
        "body",
        "footer",
        "close_label",
        "close_content",
        "extra_attrs",
    ):
        assert gone not in PJXDrawer.model_fields


def test_shell_fields_stay_minimal():
    assert set(PJXDrawer.model_fields) >= {
        "side",
        "open_on_mount",
        "remove_on_close",
        "class_name",
        "content",
    }


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone."""
    with pytest.raises(ValidationError):
        PJXDrawer(id="d", extra_attrs={"data-x": "y"})  # pyright: ignore[reportCallIssue]


class DrawerHost(BaseComponent):
    """A three-slot host, so header/body/footer compose in one tree without string joins.

    Mirrors ModalHost in tests/pyjinhx/builtins/pjx_modal/test_pjx_modal.py: a
    bare `{{ content }}` interpolation never iterates a list, so three named
    slots is the proven multi-child shape.
    """

    head: Slot = ""
    body: Slot = ""
    foot: Slot = ""


@pytest.fixture
def drawer_host_dir(tmp_path):
    """Give DrawerHost a real template on disk and repoint its descriptor at it.

    A class defined ad hoc in a test module resolves a template candidate
    co-located with the test file, which does not exist — rendering would raise
    TemplateNotFound. Same fixture shape as pjx_modal's `modal_host_dir`.
    """
    host_path = tmp_path / "drawer_host.pjx"
    host_path.write_text(
        '<div id="{{ id }}" class="drawer-host">{{ head }}{{ body }}{{ foot }}</div>'
    )
    DrawerHost.__pjx_descriptor__ = dataclasses.replace(
        DrawerHost.__pjx_descriptor__, template_path=host_path
    )
    yield tmp_path


def test_composition_order_header_body_footer(drawer_session, drawer_host_dir):
    """Header, body and footer render in document order inside one dialog root."""
    html = render(
        PJXDrawer(
            id="d",
            side="left",
            content=DrawerHost(
                id="host",
                head=PJXDrawerHeader(id="h", title="Menu"),
                body=PJXDrawerBody(id="b", content="Links"),
                foot=PJXDrawerFooter(id="f", content="v1.0"),
            ),
        ),
        drawer_session,
    )
    assert html.count("<dialog") == 1
    assert html.count("</dialog>") == 1
    assert (
        html.index("pjx-drawer__header")
        < html.index("pjx-drawer__body")
        < html.index("pjx-drawer__footer")
    )
    assert "Menu" in html
    assert "Links" in html
    assert "v1.0" in html


def test_composed_drawer_carries_the_close_affordance(drawer_session, drawer_host_dir):
    html = render(
        PJXDrawer(
            id="d",
            content=DrawerHost(
                id="host",
                head=PJXDrawerHeader(id="h", title="Nav"),
                body=PJXDrawerBody(id="b", content="Items"),
            ),
        ),
        drawer_session,
    )
    assert "data-pjx-close" in html


def test_descriptor_finds_the_snake_case_assets():
    """ADR 0007: one probe, snake_case .pjx/.css/.js — kebab-case v0.x names must not survive the port."""
    descriptor = PJXDrawer.__pjx_descriptor__
    assert descriptor.template_path is not None
    assert descriptor.template_path.name == "pjx_drawer.pjx"
    names = {path.name for path in descriptor.css_paths} | {
        path.name for path in descriptor.js_paths
    }
    assert names == {"pjx_drawer.css", "pjx_drawer.js"}
