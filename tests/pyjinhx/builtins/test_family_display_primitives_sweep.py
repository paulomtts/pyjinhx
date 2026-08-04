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

from pyjinhx import discovery
from pyjinhx._component import BaseComponent, Slot, _pascal_to_snake
from pyjinhx.builtins.ui.pjx_avatar import PJXAvatar
from pyjinhx.builtins.ui.pjx_avatar_stack import PJXAvatarStack
from pyjinhx.builtins.ui.pjx_badge import PJXBadge
from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.builtins.ui.pjx_empty_state import PJXEmptyState
from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.builtins.ui.pjx_progress import PJXProgress
from pyjinhx.builtins.ui.pjx_skeleton import PJXSkeleton
from pyjinhx.builtins.ui.pjx_spinner import PJXSpinner
from pyjinhx.classless import component
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

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
    return RenderSession()


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

    html = render(cls(id="bn", title="Ready"), session)  # pyright: ignore[reportCallIssue]

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


XSS = "<script>alert(1)</script>"


def test_string_slot_value_stays_raw_across_nested_components(family_dir, session):
    """A plain string reaching a slot two levels down is authored markup (ADR 0003), not escaped."""
    html = render(
        Wrapper(id="wrap", content=PJXEmptyState(id="empty", content=XSS)), session
    )

    assert XSS in html


def test_string_fields_escaped_when_the_component_is_a_nested_child(
    family_dir, session
):
    """Nesting does not bypass a child's own field escaping (badge label, chip label)."""
    html = render(
        Panel(
            id="panel",
            head=PJXBadge(id="badge", label=XSS),
            body=PJXEmptyState(id="empty", suggestions=[{"label": XSS}]),
            foot=PJXDivider(id="div", label=XSS),
        ),
        session,
    )

    assert "<script>" not in html
    # 4, not 3: EmptyState's chip template renders chip.label twice on purpose
    # (once as the visible button text, once as the data-pjx-suggestion attribute
    # value when chip.value is absent) — badge(1) + divider(1) + chip(2) = 4.
    assert html.count("&lt;script&gt;alert(1)&lt;/script&gt;") == 4


def test_avatar_stack_string_item_is_escaped_inside_a_nested_host(family_dir, session):
    """A raw HTML string in avatars is data, not markup, even nested two deep."""
    html = render(
        Wrapper(
            id="wrap",
            content=PJXAvatarStack(id="stack", avatars=["<b>raw</b>"]),
        ),
        session,
    )

    assert "<b>raw</b>" not in html
    assert "&lt;b&gt;raw&lt;/b&gt;" in html


def test_component_slot_value_not_double_escaped_across_nested_components(
    family_dir, session
):
    """Component-valued slots keep their markup through three hosts (Slot exemption)."""
    html = render(
        Wrapper(
            id="outer",
            content=PJXEmptyState(
                id="empty",
                content=PJXAvatarStack(
                    id="stack", avatars=[PJXAvatar(id="av", initials="AL")]
                ),
            ),
        ),
        session,
    )

    assert "&lt;div" not in html
    assert "&lt;span" not in html
    assert '<div id="av"' in html
    assert 'class="pjx-avatar__initials"' in html
    assert html.count('id="av"') == 1


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


def test_single_root_invariant_holds_three_levels_deep(family_dir, session):
    """Wrapper -> EmptyState -> AvatarStack -> Avatar still emits one root element."""
    html = render(
        Wrapper(
            id="l1",
            content=PJXEmptyState(
                id="l2",
                content=PJXAvatarStack(
                    id="l3", avatars=[PJXAvatar(id="l4", initials="AL")]
                ),
            ),
        ),
        session,
    )

    roots = _roots(html)
    assert roots == ["div"]
    for element_id in ("l1", "l2", "l3", "l4"):
        assert html.count(f'id="{element_id}"') == 1, element_id


@pytest.mark.parametrize(
    "child",
    [
        PJXBadge(id="c", label="x"),
        PJXDivider(id="c"),
        PJXDivider(id="c", orientation="vertical"),
        PJXDivider(id="c", label="Or"),
        PJXProgress(id="c", value=10),
        PJXProgress(id="c"),
        PJXSpinner(id="c"),
        PJXSkeleton(id="c", variant="circle"),
        PJXSkeleton(id="c", variant="text", lines=3),
        PJXAvatar(id="c", initials="AL"),
        PJXAvatar(id="c", src="/a.png"),
        PJXAvatarStack(id="c", avatars=[{"initials": "AL"}]),
        PJXEmptyState(id="c", content="text"),
        PJXIcon(id="c", name="check"),
    ],
    ids=lambda c: f"{type(c).__name__}",
)
def test_every_primitive_emits_one_root_when_nested(family_dir, session, child):
    """Each family member, in each of its template branches, stays single-root."""
    html = render(Wrapper(id="host", content=child), session)

    inner = html.split('class="wrapper">', 1)[1].rsplit("</div>", 1)[0]
    assert len(_roots(inner)) == 1, inner
