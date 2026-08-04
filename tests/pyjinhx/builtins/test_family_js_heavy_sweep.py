"""The JS-heavy tail exercised together in one render.

Each component here is unit-tested by its own module under
``tests/pyjinhx/builtins/pjx_*/``; this file only asserts the cross-cutting
properties those files cannot see: all eight composed in one tree, slot
placement across the family, the single-root invariant three levels deep,
escaping across a nested slot boundary, classless templates mounting several
of them at once, and — the point of this family — the ``data-pjx-*`` markers
their co-located controllers hook onto surviving composition.

There is no v2 browser suite: the v0.x Playwright suites
(``tests/reactivity/test_resizable.py``, ``tests/reactivity/test_notification_toast.py``)
have no v2 counterpart, so asserting the server-side marker contract is the
agreed stand-in. The one client-side contract that *is* covered in v2 is
``pjx.toast()``'s event dispatch, in ``tests/pyjinhx/client/test_pjx_toast.py``;
this file asserts only the server half (the host's ``data-event-name``).
"""

import dataclasses
import re
from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx.builtins.ui.pjx_alert import PJXAlert
from pyjinhx.builtins.ui.pjx_carousel import PJXCarousel
from pyjinhx.builtins.ui.pjx_carousel_slide import PJXCarouselSlide
from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.builtins.ui.pjx_notification import PJXNotification
from pyjinhx.builtins.ui.pjx_resizable_group import PJXResizableGroup
from pyjinhx.builtins.ui.pjx_resizable_handle import PJXResizableHandle
from pyjinhx.builtins.ui.pjx_resizable_panel import PJXResizablePanel
from pyjinhx.builtins.ui.pjx_toast_host import PJXToastHost
from pyjinhx.classless import component
from pyjinhx._component import BaseComponent, Slot, _pascal_to_snake
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

FAMILY = (
    PJXAlert,
    PJXNotification,
    PJXToastHost,
    PJXCarousel,
    PJXCarouselSlide,
    PJXResizableGroup,
    PJXResizableHandle,
    PJXResizablePanel,
)

MOUNTED = (*FAMILY, PJXIcon)
"""Tags needing a placeholder: the family plus PJXIcon, which pjx_carousel.pjx mounts."""


class Panel(BaseComponent):
    """A host with three independent slots, for siblings that share one parent."""

    head: Slot = ""
    body: Slot = ""
    foot: Slot = ""


class Wrapper(BaseComponent):
    """A single-slot host, used to add depth without adding markup rules."""

    content: Slot = ""


class Pair(BaseComponent):
    """A two-slot host distinct from Panel, so nesting under a Panel foot slot
    does not trip the same-class render-chain cycle guard (ADR 0004)."""

    a: Slot = ""
    b: Slot = ""


TEMPLATES = {
    "panel.pjx": (
        '<section id="{{ id }}" class="panel">'
        '<header class="panel__head">{{ head }}</header>'
        '<div class="panel__body">{{ body }}</div>'
        '<footer class="panel__foot">{{ foot }}</footer>'
        "</section>"
    ),
    "wrapper.pjx": '<div id="{{ id }}" class="wrapper">{{ content }}</div>',
    "pair.pjx": '<div id="{{ id }}" class="pair">{{ a }}{{ b }}</div>',
}


@pytest.fixture
def family_dir(tmp_path: Path):
    """Publish the family tag map under tmp_path and repoint the host descriptors.

    build_registry claims a tag only when a file named <tag>.pjx exists under
    the given directory (stem match; content is never read), so every tag this
    sweep mounts needs a placeholder or it falls back to passthrough markup.
    The hosts are then repointed at their real templates, because
    _resolve_template_path would otherwise probe this test file's directory.
    """
    for name, body in TEMPLATES.items():
        (tmp_path / name).write_text(body)
    for cls in MOUNTED:
        placeholder = tmp_path / f"{_pascal_to_snake(cls.__name__)}.pjx"
        if not placeholder.exists():
            placeholder.write_text("")
    discovery.build_registry(tmp_path, [*MOUNTED, Panel, Wrapper, Pair])
    for cls, name in (
        (Panel, "panel.pjx"),
        (Wrapper, "wrapper.pjx"),
        (Pair, "pair.pjx"),
    ):
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
    return RenderSession()


def _tree(session, **kw) -> str:
    """One Panel holding the whole family.

    head: a dismissible Alert. body: a ResizableGroup of two panels split by a
    handle, the first panel holding a Carousel with two slides. foot: a
    Notification and the ToastHost, siblings under a Pair host (not another
    Panel, to avoid the same-class render-chain cycle guard).
    """
    return render(
        Panel(
            id="panel",
            head=PJXAlert(id="alert", title="Heads up", body="saved", dismissible=True),
            body=PJXResizableGroup(
                id="group",
                content=[
                    PJXResizablePanel(
                        id="p1",
                        size=60.0,
                        content=PJXCarousel(
                            id="car",
                            content=[
                                PJXCarouselSlide(id="s1", label="One", content="a"),
                                PJXCarouselSlide(id="s2", label="Two", content="b"),
                            ],
                        ),
                    ),
                    PJXResizableHandle(id="handle"),
                    PJXResizablePanel(id="p2", content="right"),
                ],
            ),
            foot=Pair(
                id="foot",
                a=PJXNotification(id="note", content="done"),
                b=PJXToastHost(id="toast"),
            ),
            **kw,
        ),
        session,
    )


def test_nested_family_tree_renders_all_components_once(family_dir, session):
    """Every member of the family emits its own root exactly once in one tree."""
    html = _tree(session)

    for element_id in (
        "panel",
        "alert",
        "group",
        "p1",
        "car",
        "s1",
        "s2",
        "handle",
        "p2",
        "foot",
        "note",
        "toast",
    ):
        assert html.count(f'id="{element_id}"') == 1, element_id


def test_nested_family_tree_places_each_child_in_its_own_slot(family_dir, session):
    """Slot content lands inside the host region named by its field."""
    html = _tree(session)
    head = html.split('class="panel__head"')[1].split("</header>")[0]
    body = html.split('class="panel__body"')[1].split("<footer")[0]
    foot = html.split("<footer", 1)[1]

    assert 'id="alert"' in head
    assert 'id="group"' in body and 'id="handle"' in body
    assert 'id="note"' in foot and 'id="toast"' in foot
    # Group children keep their declared order: panel, handle, panel.
    assert body.index('id="p1"') < body.index('id="handle"') < body.index('id="p2"')
    # The carousel and its slides live inside the *first* panel, not the second.
    first_panel = body.split('id="p1"')[1].split('id="handle"')[0]
    assert 'id="car"' in first_panel
    assert 'id="s1"' in first_panel and 'id="s2"' in first_panel


def _roots(html: str) -> list[str]:
    """Tag names of the top-level elements in ``html`` (nesting-aware, no parser dep)."""
    depth = 0
    roots: list[str] = []
    for token in re.finditer(r"<(/?)([a-zA-Z][\w-]*)([^>]*?)(/?)>", html):
        closing, name, _attrs, self_closing = token.groups()
        void = name.lower() in {"hr", "img", "br", "input", "path", "circle", "line"}
        if closing:
            depth -= 1
            continue
        if depth == 0:
            roots.append(name)
        if not self_closing and not void:
            depth += 1
    return roots


def test_single_root_invariant_holds_four_levels_deep(family_dir, session):
    """Wrapper -> ResizablePanel -> Carousel -> Slide still emits one root element.

    ADR 0001 makes outerHTML the only OOB swap shape, so every composed node in
    this family has to stay single-root however deeply it is nested.
    """
    html = render(
        Wrapper(
            id="l1",
            content=PJXResizablePanel(
                id="l2",
                content=PJXCarousel(
                    id="l3",
                    content=[PJXCarouselSlide(id="l4", label="One", content="x")],
                ),
            ),
        ),
        session,
    )

    assert _roots(html) == ["div"]
    for element_id in ("l1", "l2", "l3", "l4"):
        assert html.count(f'id="{element_id}"') == 1, element_id


@pytest.mark.parametrize(
    "child",
    [
        PJXAlert(id="c", body="x"),
        PJXAlert(id="c", body="x", dismissible=True, title="T"),
        PJXNotification(id="c", content="x"),
        PJXNotification(id="c", content="x", autoshow=False),
        PJXToastHost(id="c"),
        PJXCarousel(id="c", content=[PJXCarouselSlide(id="s", content="x")]),
        PJXCarousel(id="c", content="x", autoplay=True),
        PJXCarouselSlide(id="c", content="x"),
        PJXResizableGroup(id="c", content=[PJXResizablePanel(id="p", content="x")]),
        PJXResizableGroup(id="c", direction="column", content="x"),
        PJXResizableHandle(id="c"),
        PJXResizablePanel(id="c", content="x"),
        PJXResizablePanel(id="c", content="x", min="120px", max="80"),
    ],
    ids=lambda c: type(c).__name__,
)
def test_every_js_heavy_builtin_emits_one_root_when_nested(family_dir, session, child):
    """Each member, in each of its template branches, stays single-root."""
    html = render(Wrapper(id="host", content=child), session)

    inner = html.split('class="wrapper">', 1)[1].rsplit("</div>", 1)[0]
    assert len(_roots(inner)) == 1, inner


XSS = '<script>alert("1") & more</script>'


def test_string_slot_value_stays_raw_across_nested_components(family_dir, session):
    """A plain string reaching a slot two levels down is authored markup (ADR 0003), not escaped."""
    html = render(Wrapper(id="wrap", content=PJXAlert(id="alert", body=XSS)), session)

    assert XSS in html


def test_string_fields_escaped_when_the_component_is_a_nested_child(
    family_dir, session
):
    """Nesting does not bypass a child's own field escaping for non-slot fields.

    `PJXResizablePanel.content` is a Slot field, so its string value stays raw
    (ADR 0003); the other three occurrences (title, label x2 aria+data) are
    plain str fields and still escape.
    """
    html = render(
        Panel(
            id="panel",
            head=PJXAlert(id="alert", title=XSS, body="ok"),
            body=PJXResizablePanel(id="p", content=XSS),
            foot=PJXCarouselSlide(id="s", label=XSS, content="ok"),
        ),
        session,
    )

    assert XSS in html  # PJXResizablePanel.content, a Slot field, stays raw
    assert html.count("&lt;script&gt;") == 3  # title, label x2 (aria + data)


def test_component_slot_value_not_double_escaped_across_nested_components(
    family_dir, session
):
    """Component-valued slots keep their markup through three hosts (Slot exemption)."""
    html = render(
        Wrapper(
            id="outer",
            content=PJXResizableGroup(
                id="group",
                content=[PJXResizablePanel(id="p", content=PJXAlert(id="a", body="x"))],
            ),
        ),
        session,
    )

    assert "&lt;div" not in html
    assert '<div class="pjx-alert' in html
    assert html.count('id="a"') == 1


def test_classless_composition_of_several_js_heavy_builtins(family_dir, session):
    """A classless template mounting three family tags renders all three, in order."""
    (family_dir / "shell.pjx").write_text(
        '{#def note: str = "hi" #}'
        '<div id="{{ id }}" class="shell">'
        '<PJXAlert id="a-{{ id }}" title="{{ note }}" dismissible="true"/>'
        '<PJXToastHost id="t-{{ id }}"/>'
        '<PJXResizableHandle id="h-{{ id }}"/>'
        "</div>"
    )
    cls = component("Shell", template_dir=family_dir)

    html = render(cls(id="sh", note="Ready"), session)  # pyright: ignore[reportCallIssue]

    assert html.index('id="a-sh"') < html.index('id="t-sh"') < html.index('id="h-sh"')
    for element_id in ("a-sh", "t-sh", "h-sh"):
        assert html.count(f'id="{element_id}"') == 1, element_id
    assert ">Ready<" in html
    assert "data-pjx-close" in html
    assert "data-pjx-toast-host" in html
    assert "data-pjx-resizable-handle" in html


def test_classless_and_componentized_composition_agree(family_dir, session):
    """Tag-mounted children produce the same child markup as Python-nested ones."""
    (family_dir / "duo.pjx").write_text(
        '<div id="{{ id }}" class="duo">'
        '<PJXToastHost id="t"/>'
        '<PJXResizableHandle id="h"/>'
        "</div>"
    )
    cls = component("Duo", template_dir=family_dir)

    classless = render(cls(id="duo"), session)

    assert render(PJXToastHost(id="t"), session).strip() in classless
    assert render(PJXResizableHandle(id="h"), session).strip() in classless


def test_alert_dismiss_marker_survives_composition(family_dir, session):
    """pjx_alert.js wires dismissal off data-pjx-close; nesting must not drop it."""
    html = _tree(session)

    assert "data-pjx-close" in html
    assert 'class="pjx-alert__dismiss"' in html
    assert 'role="status"' in html


def test_alert_without_dismissible_emits_no_dismiss_marker(family_dir, session):
    """The marker is the only dismissal contract, so it must be opt-in."""
    html = render(Wrapper(id="w", content=PJXAlert(id="a", body="x")), session)

    assert "data-pjx-close" not in html


def test_notification_client_attributes_survive_composition(family_dir, session):
    """pjx_notification.js reads data-timeout and data-pjx-autoshow off the root."""
    html = render(
        Wrapper(
            id="w",
            content=PJXNotification(
                id="note", content="done", corner="bottom-left", timeout=1200
            ),
        ),
        session,
    )

    # Corner is a class modifier, not a data attribute — asserted as shipped.
    assert "pjx-notification--bottom-left" in html
    assert 'data-timeout="1200"' in html
    assert "data-pjx-autoshow" in html
    assert "data-pjx-close" in html


def test_notification_autoshow_off_drops_only_that_marker(family_dir, session):
    html = render(
        Wrapper(id="w", content=PJXNotification(id="n", content="x", autoshow=False)),
        session,
    )

    assert "data-pjx-autoshow" not in html
    assert 'data-timeout="5000"' in html


def test_toast_host_renders_an_empty_configured_host(family_dir, session):
    """The server half of the toast contract: a configured, empty host.

    Toasts themselves are created client-side by pjx_toast_host.js, which reads
    data-event-name to know which document event to listen for; the dispatch
    half (pjx.toast fires that event on document) is covered by
    tests/pyjinhx/client/test_pjx_toast.py and is not duplicated here.
    """
    html = (
        render(
            Wrapper(
                id="w",
                content=PJXToastHost(id="toast", position="top-left", timeout=2500),
            ),
            session,
        )
        .split('class="wrapper">', 1)[1]
        .rsplit("</div>", 1)[0]
    )

    assert "data-pjx-toast-host" in html
    assert 'data-event-name="pjx:toast"' in html
    assert 'data-timeout="2500"' in html
    assert "pjx-toast-host--top-left" in html
    # Empty by design: no toast DOM is ever rendered server-side.
    assert html.strip().endswith("></div>")


def test_toast_host_custom_event_name_reaches_the_host(family_dir, session):
    html = render(PJXToastHost(id="t", event_name="app:flash"), session)

    assert 'data-event-name="app:flash"' in html


def test_carousel_markers_survive_nesting(family_dir, session):
    """The carousel controller finds every affordance through data-pjx-carousel*."""
    html = _tree(session)

    assert "data-pjx-carousel " in html or "data-pjx-carousel>" in html
    assert "data-pjx-carousel-loop" in html
    assert "data-pjx-carousel-prev" in html
    assert "data-pjx-carousel-next" in html
    assert "data-pjx-carousel-dots" in html
    # One slide marker per slide, even nested inside a resizable panel.
    assert html.count("data-pjx-carousel-slide") == 2
    assert html.count('data-pjx-carousel-label="One"') == 1


def test_carousel_autoplay_markers_are_opt_in(family_dir, session):
    """Autoplay stays opt-in: an unrequested moving region is an a11y hazard."""
    off = render(PJXCarousel(id="c", content="x"), session)
    on = render(
        PJXCarousel(id="c", content="x", autoplay=True, interval_ms=800), session
    )

    assert "data-pjx-carousel-autoplay" not in off
    assert "data-pjx-carousel-autoplay" in on
    assert 'data-pjx-carousel-interval="800"' in on
    assert "data-pjx-carousel-autoplay-toggle" in on


def test_resizable_markers_survive_composition(family_dir, session):
    """Group, handle and panel markers all survive nesting inside the family tree."""
    html = _tree(session)

    assert "data-pjx-resizable-group" in html
    assert 'data-direction="row"' in html
    assert html.count("data-pjx-resizable-panel") == 2
    assert html.count("data-pjx-resizable-handle") == 1
    assert 'role="separator"' in html
    assert 'aria-valuemin="0"' in html and 'aria-valuemax="100"' in html
    # aria-valuenow is *not* server-rendered: the controller sets it as the
    # boundary moves, so its absence here is the contract, not a gap.
    assert "aria-valuenow" not in html


def test_resizable_panel_bounds_reach_the_client_as_data_and_css(family_dir, session):
    """Percentage bounds stay data attributes; pixel floors become CSS variables."""
    html = render(
        Wrapper(
            id="w",
            content=PJXResizablePanel(id="p", size=40.0, min="120px", max=80),
        ),
        session,
    )

    assert 'data-size="40.0"' in html
    assert 'data-min="120px"' in html
    assert 'data-max="80.0"' in html
    assert "--pjx-resizable-min: 120px;" in html
    assert "--pjx-resizable-max" not in html


def test_resizable_group_inside_a_carousel_keeps_both_marker_sets(family_dir, session):
    """Cross-family composition does not let one controller's markers shadow another's."""
    html = render(
        PJXCarousel(
            id="car",
            content=[
                PJXCarouselSlide(
                    id="s",
                    content=PJXResizableGroup(
                        id="g",
                        content=[
                            PJXResizablePanel(id="p1", content="a"),
                            PJXResizableHandle(id="h"),
                            PJXResizablePanel(id="p2", content="b"),
                        ],
                    ),
                )
            ],
        ),
        session,
    )

    assert "data-pjx-carousel-slide" in html
    assert "data-pjx-resizable-group" in html
    assert html.count("data-pjx-resizable-panel") == 2
    assert "data-pjx-resizable-handle" in html
