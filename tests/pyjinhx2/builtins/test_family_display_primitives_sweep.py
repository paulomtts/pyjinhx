"""Display primitives exercised together in one render.

Each individual component is unit-tested by its own module; this file only
asserts the cross-cutting properties those files cannot see: several builtins
composed in one tree, classless templates mounting more than one of them,
escaping across a nested slot boundary, and the single-root invariant holding
three levels deep.

The builtins are plain BaseComponents with at most one slot field each, so the
multi-child shapes are declared here as host wrappers whose templates mount the
builtins by tag.
"""

import dataclasses
import re
from pathlib import Path

import pytest

from pyjinhx2 import discovery
from pyjinhx2.builtins.ui.pjx_avatar import PJXAvatar
from pyjinhx2.builtins.ui.pjx_avatar_stack import PJXAvatarStack
from pyjinhx2.builtins.ui.pjx_badge import PJXBadge
from pyjinhx2.builtins.ui.pjx_divider import PJXDivider
from pyjinhx2.builtins.ui.pjx_empty_state import PJXEmptyState
from pyjinhx2.builtins.ui.pjx_icon import PJXIcon
from pyjinhx2.builtins.ui.pjx_progress import PJXProgress
from pyjinhx2.builtins.ui.pjx_skeleton import PJXSkeleton
from pyjinhx2.builtins.ui.pjx_spinner import PJXSpinner
from pyjinhx2.classless import component
from pyjinhx2.component import BaseComponent, Slot, _pascal_to_snake
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession

FAMILY = (
    PJXIcon,
    PJXBadge,
    PJXAvatar,
    PJXAvatarStack,
    PJXDivider,
    PJXProgress,
    PJXSpinner,
    PJXSkeleton,
    PJXEmptyState,
)


class Panel(BaseComponent):
    """A host with three independent slots, for siblings that share one parent."""

    head: Slot = ""
    body: Slot = ""
    foot: Slot = ""


class Wrapper(BaseComponent):
    """A single-slot host, used to add a level of depth without adding markup rules."""

    content: Slot = ""


TEMPLATES = {
    "panel.pjx": (
        '<section id="{{ id }}" class="panel">'
        '<header class="panel__head">{{ head }}</header>'
        '<div class="panel__body">{{ body }}</div>'
        '<footer class="panel__foot">{{ foot }}</footer>'
        "</section>"
    ),
    "wrapper.pjx": '<div id="{{ id }}" class="wrapper">{{ content }}</div>',
}


@pytest.fixture
def family_dir(tmp_path: Path) -> Path:
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
    discovery.build_registry(tmp_path, [*FAMILY, Panel, Wrapper])
    for cls, name in ((Panel, "panel.pjx"), (Wrapper, "wrapper.pjx")):
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
    """A Panel holding an EmptyState (with a nested AvatarStack) plus six siblings."""
    return render(
        Panel(
            id="panel",
            head=PJXBadge(id="badge", label="New"),
            body=PJXEmptyState(
                id="empty",
                content=PJXAvatarStack(
                    id="stack",
                    avatars=[
                        PJXAvatar(id="av1", initials="AL"),
                        PJXAvatar(id="av2", initials="BO"),
                    ],
                    extra_count=3,
                ),
                suggestions=[{"label": "Retry"}],
            ),
            foot=PJXDivider(id="div"),
            **kw,
        ),
        session,
    )


def test_nested_family_tree_renders_all_components_once(family_dir, session):
    """Every component in a seven-node tree emits its own root exactly once."""
    html = _tree(session)

    for element_id in ("panel", "badge", "empty", "stack", "av1", "av2", "div"):
        assert html.count(f'id="{element_id}"') == 1, element_id


def test_nested_family_tree_places_each_child_in_its_own_slot(family_dir, session):
    """Slot content lands inside the host region named by its field."""
    html = _tree(session)
    head = html.split('class="panel__head"')[1].split("</header>")[0]
    body = html.split('class="panel__body"')[1].split("<footer")[0]

    assert 'id="badge"' in head
    assert 'id="empty"' in body
    assert 'id="stack"' in body
    assert 'id="div"' not in head and 'id="div"' not in body


def test_nested_family_tree_keeps_each_components_own_classes(family_dir, session):
    """No component's root class list is overwritten by a sibling's or parent's."""
    html = _tree(session)

    assert 'id="badge" class="pjx-badge pjx-badge--neutral pjx-badge--md"' in html
    assert 'class="pjx-empty-state"' in html
    assert 'class="pjx-avatar-stack"' in html
    assert "pjx-avatar-stack__more" in html
    assert "pjx-empty-state__chip" in html


def test_leaf_primitives_render_side_by_side_without_interfering(family_dir, session):
    """Progress, Spinner, Skeleton and Icon in one host each keep their own root."""
    html = render(
        Panel(
            id="panel",
            head=PJXProgress(id="prog", value=40, label="Uploading"),
            body=PJXSpinner(id="spin", label="Working"),
            foot=Wrapper(id="wrap", content=PJXSkeleton(id="skel", lines=2)),
        ),
        session,
    )

    assert '<div id="prog"' in html
    assert '<span id="spin"' in html
    assert '<div id="skel"' in html
    assert html.count('class="pjx-skeleton__line"') == 2
    assert html.count('id="prog"') == 1
    assert html.count('id="spin"') == 1
    assert html.count('id="skel"') == 1
    # Progress's label id is derived from its own id; a sibling must not shift it.
    assert 'aria-labelledby="prog-label"' in html


def test_icon_nested_under_a_host_keeps_its_inline_svg(family_dir, session):
    """PJXIcon's derived svg_inner is a Slot, so it survives one nesting level raw."""
    html = render(Wrapper(id="wrap", content=PJXIcon(id="ic", name="check")), session)

    assert '<svg id="ic"' in html
    assert "&lt;path" not in html
    assert html.count("<svg") == 1


def test_classless_composition_of_two_or_more_primitives(family_dir, session):
    """A {#def#} template mounting two builtins by tag renders both, in order."""
    (family_dir / "banner.pjx").write_text(
        '{#def title: str = "hi" #}'
        '<div id="{{ id }}" class="banner">'
        '<PJXBadge id="b-{{ id }}" label="{{ title }}"/>'
        '<PJXDivider id="d-{{ id }}"/>'
        "</div>"
    )
    cls = component("Banner", template_dir=family_dir)

    html = render(cls(id="bn", title="Ready"), session)

    assert html.index('id="b-bn"') < html.index('id="d-bn"')
    assert html.count('id="b-bn"') == 1
    assert html.count('id="d-bn"') == 1
    assert ">Ready<" in html


def test_classless_and_componentized_composition_agree(family_dir, session):
    """Tag-mounted children produce the same child markup as Python-nested ones."""
    (family_dir / "duo.pjx").write_text(
        '<div id="{{ id }}" class="duo">'
        '<PJXBadge id="b" label="Ready"/>'
        '<PJXDivider id="d"/>'
        "</div>"
    )
    cls = component("Duo", template_dir=family_dir)

    classless = render(cls(id="duo"), session)
    badge_alone = render(PJXBadge(id="b", label="Ready"), session)
    divider_alone = render(PJXDivider(id="d"), session)

    assert badge_alone.strip() in classless
    assert divider_alone.strip() in classless


def test_classless_host_nesting_a_classless_host(family_dir, session):
    """Two generated classes compose without either losing its own root."""
    (family_dir / "inner_box.pjx").write_text(
        '<div id="{{ id }}" class="inner"><PJXSpinner id="sp-{{ id }}"/></div>'
    )
    (family_dir / "outer_box.pjx").write_text(
        '<div id="{{ id }}" class="outer"><InnerBox id="in"/><PJXBadge id="bg" label="x"/></div>'
    )
    component("InnerBox", template_dir=family_dir)
    outer = component("OuterBox", template_dir=family_dir)

    html = render(outer(id="out"), session)

    assert html.count('id="out"') == 1
    assert html.count('id="in"') == 1
    assert html.count('id="sp-in"') == 1
    assert html.count('id="bg"') == 1
