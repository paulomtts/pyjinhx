"""Composed shells exercised together in one render, plus their MRO subclassing.

Each shell is unit-tested by its own module under ``pjx_*/``; this file only
asserts what those files cannot see: shells from different families nested in
one another, a classless template mounting shells by tag, and ADR 0010's
per-kind MRO resolution frozen into the descriptor at class-definition time.
"""

import dataclasses
import sys
import types
from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx._component import BaseComponent, Slot, _pascal_to_snake
from pyjinhx.builtins.ui.pjx_accordion import PJXAccordion
from pyjinhx.builtins.ui.pjx_accordion_content import PJXAccordionContent
from pyjinhx.builtins.ui.pjx_accordion_group import PJXAccordionGroup
from pyjinhx.builtins.ui.pjx_accordion_trigger import PJXAccordionTrigger
from pyjinhx.builtins.ui.pjx_breadcrumb import PJXBreadcrumb
from pyjinhx.builtins.ui.pjx_card import PJXCard
from pyjinhx.builtins.ui.pjx_card_body import PJXCardBody
from pyjinhx.builtins.ui.pjx_card_footer import PJXCardFooter
from pyjinhx.builtins.ui.pjx_card_header import PJXCardHeader
from pyjinhx.builtins.ui.pjx_drawer import PJXDrawer
from pyjinhx.builtins.ui.pjx_drawer_body import PJXDrawerBody
from pyjinhx.builtins.ui.pjx_drawer_footer import PJXDrawerFooter
from pyjinhx.builtins.ui.pjx_drawer_header import PJXDrawerHeader
from pyjinhx.builtins.ui.pjx_dropdown import PJXDropdown
from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.builtins.ui.pjx_modal import PJXModal
from pyjinhx.builtins.ui.pjx_modal_body import PJXModalBody
from pyjinhx.builtins.ui.pjx_modal_footer import PJXModalFooter
from pyjinhx.builtins.ui.pjx_modal_header import PJXModalHeader
from pyjinhx.builtins.ui.pjx_popover import PJXPopover
from pyjinhx.builtins.ui.pjx_popover_panel import PJXPopoverPanel
from pyjinhx.builtins.ui.pjx_popover_trigger import PJXPopoverTrigger
from pyjinhx.builtins.ui.pjx_tab import PJXTab
from pyjinhx.builtins.ui.pjx_tab_group import PJXTabGroup
from pyjinhx.builtins.ui.pjx_tab_list import PJXTabList
from pyjinhx.builtins.ui.pjx_tab_panel import PJXTabPanel
from pyjinhx.builtins.ui.pjx_tooltip import PJXTooltip
from pyjinhx.builtins.ui.pjx_tooltip_content import PJXTooltipContent
from pyjinhx.builtins.ui.pjx_tooltip_trigger import PJXTooltipTrigger
from pyjinhx.classless import component
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

FAMILY = (
    PJXCard,
    PJXCardHeader,
    PJXCardBody,
    PJXCardFooter,
    PJXModal,
    PJXModalHeader,
    PJXModalBody,
    PJXModalFooter,
    PJXDrawer,
    PJXDrawerHeader,
    PJXDrawerBody,
    PJXDrawerFooter,
    PJXAccordion,
    PJXAccordionGroup,
    PJXAccordionTrigger,
    PJXAccordionContent,
    PJXTab,
    PJXTabGroup,
    PJXTabList,
    PJXTabPanel,
    PJXPopover,
    PJXPopoverTrigger,
    PJXPopoverPanel,
    PJXTooltip,
    PJXTooltipTrigger,
    PJXTooltipContent,
    PJXDropdown,
    PJXBreadcrumb,
    PJXIcon,
)


class Panel(BaseComponent):
    """A host with three independent slots, for shells that share one parent."""

    head: Slot = ""
    body: Slot = ""
    foot: Slot = ""


class Wrapper(BaseComponent):
    """A single-slot host, used to add depth without adding markup rules."""

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
    sweep mounts needs a placeholder file. The hosts' own descriptors are then
    repointed at their real templates, because _resolve_template_path would
    otherwise probe this test file's directory.
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
    """A Panel holding a Card (with a Modal inside its body), a TabGroup and a Drawer."""
    return render(
        Panel(
            id="panel",
            head=PJXCard(
                id="card",
                content=PJXCardBody(
                    id="card-body",
                    content=PJXModal(
                        id="modal",
                        content=PJXModalHeader(id="modal-head", content="Confirm"),
                    ),
                ),
            ),
            body=PJXTabGroup(
                id="tabs",
                content=PJXTabList(
                    id="tab-list",
                    content=PJXTab(id="tab-1", panel="tab-panel-1", content="One"),
                ),
            ),
            foot=PJXDrawer(
                id="drawer",
                content=PJXDrawerFooter(id="drawer-foot", content="Close"),
            ),
            **kw,
        ),
        session,
    )


def test_cross_family_tree_renders_every_root_exactly_once(family_dir, session):
    """Card, Modal, TabGroup and Drawer nested in one Panel each emit one root."""
    html = _tree(session)

    for element_id in (
        "panel",
        "card",
        "card-body",
        "modal",
        "modal-head",
        "tabs",
        "tab-list",
        "tab-1",
        "drawer",
        "drawer-foot",
    ):
        assert html.count(f'id="{element_id}"') == 1, element_id


def test_cross_family_children_land_in_their_declared_slots(family_dir, session):
    """Each family's subtree stays inside the Panel region it was assigned to."""
    html = _tree(session)
    head = html.split('class="panel__head"')[1].split("</header>")[0]
    body = html.split('class="panel__body"')[1].split("<footer")[0]

    assert 'id="card"' in head and 'id="modal"' in head
    assert 'id="tabs"' in body and 'id="tab-1"' in body
    assert 'id="drawer"' not in head and 'id="drawer"' not in body
    assert 'id="card"' not in body


def test_each_family_keeps_its_own_root_classes(family_dir, session):
    """Sibling families do not overwrite one another's root class lists."""
    html = _tree(session)

    assert 'id="card" class="pjx-card"' in html
    assert 'class="pjx-modal' in html
    assert 'class="pjx-tab-group"' in html
    assert 'class="pjx-drawer' in html
    assert html.count("pjx-card__body") == 1
    assert html.count("pjx-drawer__footer") == 1


def test_derived_ids_do_not_collide_across_sibling_shells(family_dir, session):
    """Two Dropdowns under one host keep separate derived trigger/menu ids."""
    html = render(
        Panel(
            id="panel",
            head=PJXDropdown(id="dd-a", trigger="A", items=["one"]),
            body=PJXDropdown(id="dd-b", trigger="B", items=["two"]),
            foot=PJXBreadcrumb(id="crumbs", items=[("Home", "/"), ("Here", None)]),
        ),
        session,
    )

    for element_id in (
        "dd-a",
        "dd-a-trigger",
        "dd-a-menu",
        "dd-b",
        "dd-b-trigger",
        "dd-b-menu",
        "crumbs",
    ):
        assert html.count(f'id="{element_id}"') == 1, element_id


def test_four_families_deep_keep_one_root_each(family_dir, session):
    """Wrapper -> Accordion -> Card -> Popover -> Tooltip nests without loss."""
    html = render(
        Wrapper(
            id="w",
            content=PJXAccordionGroup(
                id="ag",
                content=PJXAccordion(
                    id="acc",
                    content=PJXAccordionContent(
                        id="acc-body",
                        content=PJXCard(
                            id="card",
                            content=PJXPopover(
                                id="pop",
                                content=PJXPopoverPanel(
                                    id="pop-panel",
                                    content=PJXTooltip(
                                        id="tip",
                                        content=PJXTooltipContent(
                                            id="tip-body", content="Hi"
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        session,
    )

    for element_id in (
        "w",
        "ag",
        "acc",
        "acc-body",
        "card",
        "pop",
        "pop-panel",
        "tip",
        "tip-body",
    ):
        assert html.count(f'id="{element_id}"') == 1, element_id
    assert html.startswith('<div id="w" class="wrapper">')
    assert html.endswith("</div>")


def test_classless_template_mounts_two_shell_families(family_dir, session):
    """A generated class mounting Card and Dropdown by tag renders both, in order."""
    (family_dir / "toolbar.pjx").write_text(
        '{#def label: str = "Menu" #}'
        '<div id="{{ id }}" class="toolbar">'
        '<PJXCard id="c-{{ id }}"/>'
        '<PJXDropdown id="d-{{ id }}" trigger="{{ label }}"/>'
        "</div>"
    )
    cls = component("Toolbar", template_dir=family_dir)

    html = render(cls(id="tb", label="More"), session)  # pyright: ignore[reportCallIssue]

    assert html.index('id="c-tb"') < html.index('id="d-tb"')
    assert html.count('id="c-tb"') == 1
    assert html.count('id="d-tb"') == 1
    assert ">More<" in html


def test_unknown_pascal_tag_beside_a_shell_passes_through(family_dir, session):
    """A tag with no class in the registry is left as-is; the real shell still renders."""
    (family_dir / "mixed_bar.pjx").write_text(
        '<div id="{{ id }}" class="mixed"><PJXCard id="known"/><PJXNotAThing/></div>'
    )
    cls = component("MixedBar", template_dir=family_dir)

    html = render(cls(id="mb"), session)

    assert "<PJXNotAThing" in html
    assert 'id="known" class="pjx-card"' in html


def _module_at(tmp_path: Path, name: str) -> types.ModuleType:
    """A real module object whose __file__ lives under tmp_path.

    Template and asset candidates are computed from the defining module's
    directory, so subclasses defined here probe tmp_path — letting a test plant
    a .css/.js beside a subclass without writing files into the test tree.
    """
    module = types.ModuleType(name)
    module.__file__ = str(tmp_path / f"{name}.py")
    sys.modules[name] = module
    return module


@pytest.fixture
def subclass_module(family_dir: Path):
    """A throwaway module under family_dir, unregistered from sys.modules after."""
    module = _module_at(family_dir, "pjx_sweep_subclasses")
    yield module
    del sys.modules["pjx_sweep_subclasses"]


def _define_subclass(
    module: types.ModuleType, source: str, name: str, **globals_: object
):
    """Define a component subclass inside ``module`` and return it.

    exec, not a plain class statement, because __module__ decides which
    directory the descriptor probes — and that must be tmp_path, not this file.
    """
    namespace = dict(module.__dict__)
    namespace["__name__"] = module.__name__
    namespace.update(globals_)
    exec(source, namespace)  # noqa: S102 — only way to define a class in a synthetic module
    cls = namespace[name]
    setattr(module, name, cls)
    return cls


def test_card_subclass_inherits_template_and_overrides_css(family_dir, subclass_module):
    """Per ADR 0010 the two kinds walk independently: template from PJXCard, css from the subclass."""
    (family_dir / "fancy_card.css").write_text(".fancy-card{}")
    cls = _define_subclass(
        subclass_module,
        "class FancyCard(PJXCard):\n    pass\n",
        "FancyCard",
        PJXCard=PJXCard,
    )

    descriptor = cls.__pjx_descriptor__
    assert descriptor.template_path == PJXCard.__pjx_descriptor__.template_path
    assert descriptor.css_paths == (family_dir / "fancy_card.css",)
    # _walk_template returns the last ancestor's candidate *unprobed* (ADR
    # 0007's budget) when nothing nearer owns a template, so _resolve_provenance
    # omits the "template" key entirely rather than naming an unproven owner —
    # it is never set to PJXCard here. See _component.py::_resolve_provenance.
    assert "template" not in descriptor.provenance
    assert descriptor.provenance["css"] is cls


def test_modal_subclass_inherits_template_and_css_but_owns_its_js(
    family_dir, subclass_module
):
    """A subclass adding only a script keeps the parent's template and stylesheet."""
    (family_dir / "wizard_modal.js").write_text("// wizard")
    cls = _define_subclass(
        subclass_module,
        "class WizardModal(PJXModal):\n    pass\n",
        "WizardModal",
        PJXModal=PJXModal,
    )

    descriptor = cls.__pjx_descriptor__
    assert descriptor.template_path == PJXModal.__pjx_descriptor__.template_path
    assert descriptor.css_paths == PJXModal.__pjx_descriptor__.css_paths
    assert descriptor.js_paths == (family_dir / "wizard_modal.js",)
    assert descriptor.provenance["css"] is PJXModal
    assert descriptor.provenance["js"] is cls


def test_accordion_grandchild_takes_template_from_grandparent_and_css_from_parent(
    family_dir, subclass_module
):
    """Each kind stops at its own nearest owner — they need not be the same ancestor."""
    (family_dir / "themed_accordion.css").write_text(".themed{}")
    parent = _define_subclass(
        subclass_module,
        "class ThemedAccordion(PJXAccordion):\n    pass\n",
        "ThemedAccordion",
        PJXAccordion=PJXAccordion,
    )
    child = _define_subclass(
        subclass_module,
        "class CompactAccordion(ThemedAccordion):\n    pass\n",
        "CompactAccordion",
        ThemedAccordion=parent,
    )

    descriptor = child.__pjx_descriptor__
    assert descriptor.template_path == PJXAccordion.__pjx_descriptor__.template_path
    assert descriptor.css_paths == (family_dir / "themed_accordion.css",)
    # Same unprobed-fallback rule as the Card case: the template answer comes
    # from the last (unprobed) ancestor candidate, so no "template" provenance
    # key is recorded — only css, which a real probe (ThemedAccordion) proved.
    assert "template" not in descriptor.provenance
    assert descriptor.provenance["css"] is parent


def test_subclass_resolution_is_frozen_at_class_definition_not_at_render(
    family_dir, subclass_module, session
):
    """The descriptor is final the moment the class statement returns.

    A .css planted after definition is ignored, and a css planted before is
    already recorded — so nothing about resolution can be happening at render.
    """
    cls = _define_subclass(
        subclass_module,
        "class PlainCard(PJXCard):\n    pass\n",
        "PlainCard",
        PJXCard=PJXCard,
    )
    before_render = cls.__pjx_descriptor__

    assert before_render.template_path == PJXCard.__pjx_descriptor__.template_path
    assert before_render.css_paths == PJXCard.__pjx_descriptor__.css_paths

    (family_dir / "plain_card.css").write_text(".late{}")
    html = render(cls(id="pc", content="text"), session)

    assert cls.__pjx_descriptor__ is before_render
    assert cls.__pjx_descriptor__.css_paths == PJXCard.__pjx_descriptor__.css_paths
    assert 'id="pc" class="pjx-card"' in html


def test_subclass_with_no_template_renders_its_parents_markup(
    family_dir, subclass_module, session
):
    """A three-line subclass is a usable component: no template file of its own."""
    cls = _define_subclass(
        subclass_module,
        'class LoudCard(PJXCard):\n    class_name: str = "loud"\n',
        "LoudCard",
        PJXCard=PJXCard,
    )

    html = render(
        cls(id="lc", content=PJXCardHeader(id="lch", content="Title")), session
    )

    assert html.startswith('<article id="lc" class="pjx-card loud">')
    assert html.count('id="lch"') == 1
