"""The JS-heavy tail exercised together in one render.

Each component here is unit-tested by its own module under
``tests/pyjinhx2/builtins/pjx_*/``; this file only asserts the cross-cutting
properties those files cannot see: all eight composed in one tree, slot
placement across the family, the single-root invariant three levels deep,
escaping across a nested slot boundary, classless templates mounting several
of them at once, and — the point of this family — the ``data-pjx-*`` markers
their co-located controllers hook onto surviving composition.

There is no v2 browser suite: the v0.x Playwright suites
(``tests/reactivity/test_resizable.py``, ``tests/reactivity/test_notification_toast.py``)
have no v2 counterpart, so asserting the server-side marker contract is the
agreed stand-in. The one client-side contract that *is* covered in v2 is
``pjx.toast()``'s event dispatch, in ``tests/pyjinhx2/client/test_pjx_toast.py``;
this file asserts only the server half (the host's ``data-event-name``).
"""

import dataclasses
from pathlib import Path

import pytest

from pyjinhx2 import discovery
from pyjinhx2.builtins.ui.pjx_alert import PJXAlert
from pyjinhx2.builtins.ui.pjx_carousel import PJXCarousel
from pyjinhx2.builtins.ui.pjx_carousel_slide import PJXCarouselSlide
from pyjinhx2.builtins.ui.pjx_icon import PJXIcon
from pyjinhx2.builtins.ui.pjx_notification import PJXNotification
from pyjinhx2.builtins.ui.pjx_resizable_group import PJXResizableGroup
from pyjinhx2.builtins.ui.pjx_resizable_handle import PJXResizableHandle
from pyjinhx2.builtins.ui.pjx_resizable_panel import PJXResizablePanel
from pyjinhx2.builtins.ui.pjx_toast_host import PJXToastHost
from pyjinhx2.component import BaseComponent, Slot, _pascal_to_snake
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession

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
    return RenderSession(template_dir="/")


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
