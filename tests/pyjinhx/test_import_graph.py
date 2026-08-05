"""The declared import direction for pyjinhx, enforced statically.

_component.py sits below descriptor.py and must never reach up into it for
anything but the one sanctioned edge: the ClassDescriptor it builds and attaches
in __pydantic_init_subclass__ (#271). It also reaches up into rendering.py and
session.py, but only from inside BaseComponent.render()'s method body — never at
module scope, since rendering.py imports BaseComponent at import time and a
module-level edge back would be a real cycle (#643). descriptor.py and segments.py are
import-pure — stdlib only. Per-module purity is also asserted in
test_descriptor.py and test_segments.py; this file is the whole-package view, so
a new module cannot quietly add an edge nobody declared.
"""

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "pyjinhx"

# Every internal edge pyjinhx is allowed to have, module -> modules it may
# import. A module absent from a value list may not be imported by that key.
# Add an entry here deliberately when a new edge is designed, never to make a
# failing test go green.
ALLOWED_INTERNAL_IMPORTS: dict[str, frozenset[str]] = {
    "__init__": frozenset(),
    # The TYPE_CHECKING-only RenderSession import mirrors session's own
    # component/segments entries below, for the same reason: the enum/function
    # signature names the type, runtime never touches it.
    # component is a real runtime edge: all_assets() reads
    # BaseComponent.__subclasses__() and each class's descriptor, imported
    # locally to avoid a module-level cycle (session imports assets).
    "assets": frozenset({"pyjinhx.session", "pyjinhx._component"}),
    # app_context is import-pure - stdlib only - so the reactive load() wrap can
    # import it at module scope without threading an edge back into the spine.
    "app_context": frozenset(),
    # builtins/ ports v0.x's component library onto the v2 stack, one leaf
    # package per component (#500). Each leaf only reaches down into
    # _component.py for BaseComponent/Slot/AttrValue and its own vendored
    # data module; nothing above the leaf imports back.
    "builtins.__init__": frozenset(),
    "builtins.ui.__init__": frozenset(),
    "builtins.ui.pjx_badge.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_badge.pjx_badge"}
    ),
    "builtins.ui.pjx_badge.pjx_badge": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_avatar.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_avatar.pjx_avatar"}
    ),
    "builtins.ui.pjx_avatar.pjx_avatar": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_avatar_stack.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_avatar_stack.pjx_avatar_stack"}
    ),
    "builtins.ui.pjx_avatar_stack.pjx_avatar_stack": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_divider.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_divider.pjx_divider"}
    ),
    "builtins.ui.pjx_divider.pjx_divider": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_progress.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_progress.pjx_progress"}
    ),
    "builtins.ui.pjx_progress.pjx_progress": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_button.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_button.pjx_button"}
    ),
    # #693: the loading spinner is composed in Python as a component-typed
    # field instead of a <PJXRegionLoader/> tag literal, so this leaf now also
    # reaches down into the pjx_region_loader leaf.
    "builtins.ui.pjx_button.pjx_button": frozenset(
        {"pyjinhx._component", "pyjinhx.builtins.pjx_region_loader"}
    ),
    "builtins.ui.pjx_chip_input.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_chip_input.pjx_chip_input"}
    ),
    "builtins.ui.pjx_chip_input.pjx_chip_input": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_form_field.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_form_field.pjx_form_field"}
    ),
    "builtins.ui.pjx_form_field.pjx_form_field": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_password_input.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_password_input.pjx_password_input"}
    ),
    "builtins.ui.pjx_password_input.pjx_password_input": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_segmented_control.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_segmented_control.pjx_segmented_control"}
    ),
    "builtins.ui.pjx_segmented_control.pjx_segmented_control": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_toggle_switch.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_toggle_switch.pjx_toggle_switch"}
    ),
    "builtins.ui.pjx_toggle_switch.pjx_toggle_switch": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_spinner.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_spinner.pjx_spinner"}
    ),
    "builtins.ui.pjx_spinner.pjx_spinner": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_skeleton.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_skeleton.pjx_skeleton"}
    ),
    "builtins.ui.pjx_skeleton.pjx_skeleton": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_empty_state.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_empty_state.pjx_empty_state"}
    ),
    "builtins.ui.pjx_empty_state.pjx_empty_state": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_card.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_card.pjx_card"}
    ),
    "builtins.ui.pjx_card.pjx_card": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_card_header.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_card_header.pjx_card_header"}
    ),
    "builtins.ui.pjx_card_header.pjx_card_header": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_card_body.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_card_body.pjx_card_body"}
    ),
    "builtins.ui.pjx_card_body.pjx_card_body": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_card_footer.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_card_footer.pjx_card_footer"}
    ),
    "builtins.ui.pjx_card_footer.pjx_card_footer": frozenset({"pyjinhx._component"}),
    # pjx_modal family (#517): the dialog shell plus its header/body/footer
    # regions. Each component module reaches down into _component.py only; each
    # __init__ just re-exports its class from its co-located module.
    "builtins.ui.pjx_modal.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_modal.pjx_modal"}
    ),
    "builtins.ui.pjx_modal.pjx_modal": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_modal_header.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_modal_header.pjx_modal_header"}
    ),
    "builtins.ui.pjx_modal_header.pjx_modal_header": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_modal_body.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_modal_body.pjx_modal_body"}
    ),
    "builtins.ui.pjx_modal_body.pjx_modal_body": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_modal_footer.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_modal_footer.pjx_modal_footer"}
    ),
    "builtins.ui.pjx_modal_footer.pjx_modal_footer": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_confirm_dialog.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_confirm_dialog.pjx_confirm_dialog"}
    ),
    "builtins.ui.pjx_confirm_dialog.pjx_confirm_dialog": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_prompt_dialog.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_prompt_dialog.pjx_prompt_dialog"}
    ),
    "builtins.ui.pjx_prompt_dialog.pjx_prompt_dialog": frozenset(
        {"pyjinhx._component"}
    ),
    # pjx_drawer family (#518): the slide-in dialog shell plus its
    # header/body/footer regions. Same shape as the modal family — each
    # component module reaches down into _component.py only; each __init__ just
    # re-exports its class from its co-located module.
    "builtins.ui.pjx_drawer.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_drawer.pjx_drawer"}
    ),
    "builtins.ui.pjx_drawer.pjx_drawer": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_drawer_header.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_drawer_header.pjx_drawer_header"}
    ),
    "builtins.ui.pjx_drawer_header.pjx_drawer_header": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_drawer_body.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_drawer_body.pjx_drawer_body"}
    ),
    "builtins.ui.pjx_drawer_body.pjx_drawer_body": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_drawer_footer.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_drawer_footer.pjx_drawer_footer"}
    ),
    "builtins.ui.pjx_drawer_footer.pjx_drawer_footer": frozenset(
        {"pyjinhx._component"}
    ),
    # pjx_accordion family (#519): the details/summary shell plus its
    # group/trigger/content parts. Same shape as the modal/drawer families —
    # each component module reaches down into _component.py only; each
    # __init__ just re-exports its class from its co-located module.
    "builtins.ui.pjx_accordion.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_accordion.pjx_accordion"}
    ),
    "builtins.ui.pjx_accordion.pjx_accordion": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_accordion_content.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_accordion_content.pjx_accordion_content"}
    ),
    "builtins.ui.pjx_accordion_content.pjx_accordion_content": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_accordion_group.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_accordion_group.pjx_accordion_group"}
    ),
    "builtins.ui.pjx_accordion_group.pjx_accordion_group": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_accordion_trigger.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_accordion_trigger.pjx_accordion_trigger"}
    ),
    # #693: the chevron is composed in Python as a component-typed field
    # instead of a <PJXIcon/> tag literal, so this leaf now also reaches down
    # into the pjx_icon leaf.
    "builtins.ui.pjx_accordion_trigger.pjx_accordion_trigger": frozenset(
        {"pyjinhx._component", "pyjinhx.builtins.ui.pjx_icon"}
    ),
    # pjx_tab family (#520): the group shell, its tablist, the tab triggers
    # and the panels they reveal. Only the group carries JS; the tab template
    # reaches PJXIcon through discovery's tag map, not a Python import, so no
    # leaf gains an edge beyond _component.py.
    "builtins.ui.pjx_tab_group.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_tab_group.pjx_tab_group"}
    ),
    "builtins.ui.pjx_tab_group.pjx_tab_group": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_tab_list.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_tab_list.pjx_tab_list"}
    ),
    "builtins.ui.pjx_tab_list.pjx_tab_list": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_tab.__init__": frozenset({"pyjinhx.builtins.ui.pjx_tab.pjx_tab"}),
    "builtins.ui.pjx_tab.pjx_tab": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_tab_panel.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_tab_panel.pjx_tab_panel"}
    ),
    "builtins.ui.pjx_tab_panel.pjx_tab_panel": frozenset({"pyjinhx._component"}),
    # pjx_popover family (#521): the positioned root shell, its trigger, and
    # the panel it reveals. JS/CSS live only on the root; each leaf reaches
    # _component.py only.
    "builtins.ui.pjx_popover.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_popover.pjx_popover"}
    ),
    "builtins.ui.pjx_popover.pjx_popover": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_popover_trigger.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_popover_trigger.pjx_popover_trigger"}
    ),
    "builtins.ui.pjx_popover_trigger.pjx_popover_trigger": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_popover_panel.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_popover_panel.pjx_popover_panel"}
    ),
    "builtins.ui.pjx_popover_panel.pjx_popover_panel": frozenset(
        {"pyjinhx._component"}
    ),
    # pjx_tooltip family (#522): the positioned root shell, its focusable
    # trigger, and the hidden tip. JS/CSS live only on the root; each leaf
    # reaches _component.py only.
    "builtins.ui.pjx_tooltip.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_tooltip.pjx_tooltip"}
    ),
    "builtins.ui.pjx_tooltip.pjx_tooltip": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_tooltip_trigger.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_tooltip_trigger.pjx_tooltip_trigger"}
    ),
    "builtins.ui.pjx_tooltip_trigger.pjx_tooltip_trigger": frozenset(
        {"pyjinhx._component"}
    ),
    # pjx_dropdown family (#523): a single trigger+menu component reusing
    # the pjx_popover JS runtime. #695 turned that reuse into a real MRO
    # edge — PJXDropdown extends PJXPopover so the descriptor's asset walk
    # inherits pjx_popover.js instead of shipping the markup contract with
    # no script behind it.
    "builtins.ui.pjx_dropdown.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_dropdown.pjx_dropdown"}
    ),
    "builtins.ui.pjx_dropdown.pjx_dropdown": frozenset(
        {"pyjinhx._component", "pyjinhx.builtins.ui.pjx_popover"}
    ),
    "builtins.ui.pjx_breadcrumb.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_breadcrumb.pjx_breadcrumb"}
    ),
    "builtins.ui.pjx_breadcrumb.pjx_breadcrumb": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_tooltip_content.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_tooltip_content.pjx_tooltip_content"}
    ),
    "builtins.ui.pjx_tooltip_content.pjx_tooltip_content": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_notification.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_notification.pjx_notification"}
    ),
    "builtins.ui.pjx_notification.pjx_notification": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_alert.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_alert.pjx_alert"}
    ),
    "builtins.ui.pjx_alert.pjx_alert": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_toast_host.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_toast_host.pjx_toast_host"}
    ),
    "builtins.ui.pjx_toast_host.pjx_toast_host": frozenset({"pyjinhx._component"}),
    "builtins.ui.pjx_icon.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_icon.pjx_icon"}
    ),
    "builtins.ui.pjx_icon._icons": frozenset(),
    "builtins.ui.pjx_icon.pjx_icon": frozenset(
        {"pyjinhx._component", "pyjinhx.builtins.ui.pjx_icon._icons"}
    ),
    "builtins.ui.pjx_carousel.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_carousel.pjx_carousel"}
    ),
    # #693: the four arrow/autoplay icons are composed in Python as
    # component-typed fields instead of <PJXIcon/> tag literals, so this leaf
    # now also reaches down into the pjx_icon leaf.
    "builtins.ui.pjx_carousel.pjx_carousel": frozenset(
        {"pyjinhx._component", "pyjinhx.builtins.ui.pjx_icon"}
    ),
    "builtins.ui.pjx_carousel_slide.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_carousel_slide.pjx_carousel_slide"}
    ),
    "builtins.ui.pjx_carousel_slide.pjx_carousel_slide": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_resizable_group.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_resizable_group.pjx_resizable_group"}
    ),
    "builtins.ui.pjx_resizable_group.pjx_resizable_group": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_resizable_panel.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_resizable_panel.pjx_resizable_panel"}
    ),
    "builtins.ui.pjx_resizable_panel.pjx_resizable_panel": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.ui.pjx_resizable_handle.__init__": frozenset(
        {"pyjinhx.builtins.ui.pjx_resizable_handle.pjx_resizable_handle"}
    ),
    "builtins.ui.pjx_resizable_handle.pjx_resizable_handle": frozenset(
        {"pyjinhx._component"}
    ),
    # The classless factory is a consumer: it validates a tag name, reads the
    # template discovery found, hands the header to props_header and publishes
    # the result through discovery's own write path. Nothing imports it back.
    "classless": frozenset(
        {
            "pyjinhx",
            "pyjinhx._component",
            "pyjinhx.discovery",
            "pyjinhx.props_header",
            "pyjinhx.segments",
        }
    ),
    # The client tier is the bottom of the stack: it ships pjx.js and reads it
    # off disk. Nothing in pyjinhx may be imported from here, or the browser
    # runtime's delivery would depend on the server tier that serves it.
    "client.__init__": frozenset(),
    # The one sanctioned edge out of the client tier: inject.py writes the
    # runtime payload onto RenderSession and gates on js_mode, mirroring the
    # "dotted edge" architecture-overview.md calls out between L2's
    # RenderSession and L3 (cold render's assets flow through the session).
    "client.inject": frozenset({"pyjinhx.assets", "pyjinhx.client", "pyjinhx.session"}),
    # descriptor/props_header are ordinary upward reads. render and session are
    # the reverse edges behind BaseComponent.render(): both are imported inside
    # the method body, never at module scope, because rendering.py imports
    # BaseComponent at import time and a module-level edge back would be a real
    # cycle — the same local-import escape hatch assets.py already uses.
    "_component": frozenset(
        {
            "pyjinhx.descriptor",
            "pyjinhx.props_header",
            "pyjinhx.rendering",
            "pyjinhx.session",
        }
    ),
    # config sits above everything: it may read the spine to register
    # components and it defers to siblings that own the app wiring and dev
    # tooling. The reverse edge — any spine, reactive/ or client/ module
    # importing config — stays forbidden and is asserted below.
    "config": frozenset(
        {
            "pyjinhx",
            "pyjinhx._component",
            "pyjinhx.discovery",
            "pyjinhx.dev",
            "pyjinhx.integrations.base",
            "pyjinhx.integrations.fastapi",
        }
    ),
    # context sits above the spine with config and integrations.fastapi: it is a
    # read-only view over session's ContextVars plus the pjx state the FastAPI
    # middleware parsed onto the request. Request is typed from starlette, never
    # imported from integrations.fastapi, so the adapter keeps zero importers
    # below it. Nothing in the spine may import context back.
    "context": frozenset({"pyjinhx.session"}),
    "descriptor": frozenset(),
    # dev sits above the spine, next to config and context: it walks
    # BaseComponent's subclass tree for the dependency graph and reads the
    # request-scoped dirtied set and cache reverse index for its checks. config
    # imports it (deferred); nothing below may import it back.
    "dev": frozenset({"pyjinhx._component", "pyjinhx.session"}),
    # discovery keys the registry by each class's own resolved tag, so it reads
    # _component.py's snake-case helper rather than inventing a second naming
    # scheme that could drift from the one templates are probed with.
    "discovery": frozenset({"pyjinhx._component"}),
    # The framework adapter sits at the very top with config: it orchestrates
    # the request cycle by calling published entry points (request_scope,
    # render, inject_runtime, compose) and nothing imports it back
    # except config's deferred setup() edge. It reads integrations.base for the
    # Protocol's shared names and to register itself at import time.
    "integrations.__init__": frozenset(),
    # base defines the backend-agnostic Protocol other adapters implement; it
    # only touches session.py's request_scope() by documented contract, never
    # by import, so it has no internal edges of its own.
    "integrations.base": frozenset(),
    "integrations.fastapi": frozenset(
        {
            "pyjinhx.client.inject",
            "pyjinhx._component",
            "pyjinhx.config",
            "pyjinhx.integrations.base",
            "pyjinhx.reactive.root_attrs",
            "pyjinhx.registry",
            "pyjinhx.responses",
            "pyjinhx.session",
        }
    ),
    "markers": frozenset({"pyjinhx._component"}),
    # Generating a class from a {#def #} header needs the open-model base to
    # subclass; parsing itself stays pure.
    "props_header": frozenset({"pyjinhx._component"}),
    # rendering resolves each ChildRef tag against the published class registry;
    # an unregistered tag is emitted verbatim, so this is a read-only edge.
    "rendering": frozenset(
        {
            "pyjinhx.assets",
            "pyjinhx._component",
            "pyjinhx.discovery",
            "pyjinhx.markers",
            "pyjinhx.props_header",
            "pyjinhx.render_context",
            "pyjinhx.segments",
            "pyjinhx.session",
        }
    ),
    "render_context": frozenset({"pyjinhx.markers", "pyjinhx._component"}),
    "reactive.__init__": frozenset(),
    "reactive.keys": frozenset(),
    # The tier-2 cache seam: a protocol and a reference in-memory implementation,
    # both self-contained on stdlib. Nothing here reaches into tier 1 (cache.py)
    # or the render spine - wiring it in is a later subtask's edge to add.
    "reactive.backend": frozenset(),
    # cache.py is a store over session's cache ContextVar and nothing else: it
    # owns no state, and it must not reach sideways into keys.py or up into the
    # render spine to key or evict anything.
    "reactive.cache": frozenset({"pyjinhx.session"}),
    # mutations.py records dirtied keys through session's public writer; it owns
    # no ContextVar of its own and never reaches sideways into cache.py.
    "reactive.mutations": frozenset({"pyjinhx.session", "pyjinhx.reactive.keys"}),
    # #490: which of a fan-out's required assets the client is missing, read
    # from the candidates' frozen descriptors (not session accumulation - see
    # the module docstring) and diffed against asset_token()'s identity.
    "reactive.assets": frozenset(
        {
            "pyjinhx.assets",
            "pyjinhx.reactive.fanout",
            "pyjinhx.session",
        }
    ),
    # ReactiveComponent subclasses BaseComponent and routes load() through the
    # cache: the two edges below are the whole design. The reverse - anything in
    # the render spine importing reactive/ - stays forbidden.
    # The load() wrap resolves its app-context parameter through app_context and
    # reads the bound value out of session's ContextVar; both are strictly below
    # reactive/, so neither edge is a cycle.
    "reactive.component": frozenset(
        {
            "pyjinhx.app_context",
            "pyjinhx._component",
            "pyjinhx.reactive.cache",
            "pyjinhx.reactive.keys",
            "pyjinhx.session",
        }
    ),
    # The reactive on_rendered branch (#463): it reads ReactiveComponent to
    # decide whether to act and reuses the spine's one splice primitive. Every
    # edge points downward into the spine — root_attrs/segments/session know
    # nothing about this module, and rendering.py never imports it.
    "reactive.root_attrs": frozenset(
        {
            "pyjinhx._component",
            "pyjinhx.reactive.component",
            # coerce_load_key_str: data-pjx-load must be stamped through the
            # same coercion fanout's _load_key() reads it back with (E16), or
            # the two spellings of one key would not compare equal.
            "pyjinhx.reactive.keys",
            "pyjinhx.root_attrs",
            "pyjinhx.segments",
            "pyjinhx.session",
        }
    ),
    # The L3.5.1 manifest walk (#466): read-only against discovery (tag ->
    # class), the registry (resolve() only, never register_instance - E7),
    # and the load cache (a separate key space, E13). It re-renders a dirty
    # candidate through render_level(), the same primitive root_attrs.py
    # uses, and falls back to current_session() rather than ever building an
    # unscoped RenderSession with the wrong template_dir. #468 adds the
    # structural nesting dedup pass, which walks segments/ChildRef directly
    # rather than re-parsing or substring-matching rendered markup.
    "reactive.fanout": frozenset(
        {
            "pyjinhx",
            "pyjinhx.discovery",
            "pyjinhx.registry",
            "pyjinhx.reactive.cache",
            "pyjinhx.reactive.component",
            "pyjinhx.reactive.keys",
            "pyjinhx.rendering",
            "pyjinhx.root_attrs",
            "pyjinhx.segments",
            "pyjinhx.session",
        }
    ),
    # The instance registry (ADR 0009) is read-only over session's ContextVar
    # store; it consumes get_instances() and nothing else in pyjinhx. The
    # register_rendered_instance signature also names RenderedLevel, but that
    # import is TYPE_CHECKING-only (see registry.py) — never a runtime edge.
    "registry": frozenset({"pyjinhx.session", "pyjinhx.segments"}),
    "root_attrs": frozenset({"pyjinhx.segments"}),
    # The framework-free response layer every backend funnels handler returns
    # through. It reaches down into the render spine to build a primary body and
    # sideways into reactive/ for the two fan-out legs; nothing imports it back
    # except the integrations, so these edges cannot become a cycle.
    "responses": frozenset(
        {
            "pyjinhx._component",
            "pyjinhx.reactive.assets",
            "pyjinhx.reactive.cache",
            "pyjinhx.reactive.fanout",
            "pyjinhx.rendering",
            "pyjinhx.session",
        }
    ),
    "segments": frozenset(),
    # The on_rendered hook's signature names BaseComponent and RenderedLevel, but
    # both imports are TYPE_CHECKING-only. At runtime session also imports
    # AssetMode from assets, a real edge alongside markers.
    # session owns the per-request ContextVars. The one upward edge is
    # config, imported inside request_scope()'s body — never at module scope
    # — so the default session can be seeded with the app's Jinja globals and
    # filters without inverting the layering; see the function-local guard
    # test below.
    "session": frozenset(
        {
            "pyjinhx.markers",
            "pyjinhx._component",
            "pyjinhx.segments",
            "pyjinhx.assets",
            "pyjinhx.config",
        }
    ),
    # pjx_table family (#526): each component module imports only the core
    # component surface (AttrValue, BaseComponent, Slot); each __init__ just
    # re-exports its class from its co-located module.
    "builtins.pjx_table.__init__": frozenset({"pyjinhx.builtins.pjx_table.pjx_table"}),
    "builtins.pjx_table.pjx_table": frozenset({"pyjinhx._component"}),
    "builtins.pjx_table_head.__init__": frozenset(
        {"pyjinhx.builtins.pjx_table_head.pjx_table_head"}
    ),
    "builtins.pjx_table_head.pjx_table_head": frozenset({"pyjinhx._component"}),
    "builtins.pjx_table_body.__init__": frozenset(
        {"pyjinhx.builtins.pjx_table_body.pjx_table_body"}
    ),
    "builtins.pjx_table_body.pjx_table_body": frozenset({"pyjinhx._component"}),
    "builtins.pjx_table_row.__init__": frozenset(
        {"pyjinhx.builtins.pjx_table_row.pjx_table_row"}
    ),
    "builtins.pjx_table_row.pjx_table_row": frozenset({"pyjinhx._component"}),
    "builtins.pjx_table_header_cell.__init__": frozenset(
        {"pyjinhx.builtins.pjx_table_header_cell.pjx_table_header_cell"}
    ),
    "builtins.pjx_table_header_cell.pjx_table_header_cell": frozenset(
        {"pyjinhx._component"}
    ),
    "builtins.pjx_table_cell.__init__": frozenset(
        {"pyjinhx.builtins.pjx_table_cell.pjx_table_cell"}
    ),
    "builtins.pjx_table_cell.pjx_table_cell": frozenset({"pyjinhx._component"}),
    "builtins.pjx_paginator.__init__": frozenset(
        {"pyjinhx.builtins.pjx_paginator.pjx_paginator"}
    ),
    "builtins.pjx_paginator.pjx_paginator": frozenset({"pyjinhx._component"}),
    "builtins.pjx_lazy_load.__init__": frozenset(
        {"pyjinhx.builtins.pjx_lazy_load.pjx_lazy_load"}
    ),
    "builtins.pjx_lazy_load.pjx_lazy_load": frozenset({"pyjinhx._component"}),
    "builtins.pjx_region_loader.__init__": frozenset(
        {"pyjinhx.builtins.pjx_region_loader.pjx_region_loader"}
    ),
    "builtins.pjx_region_loader.pjx_region_loader": frozenset({"pyjinhx._component"}),
    "builtins.pjx_page_loader.__init__": frozenset(
        {"pyjinhx.builtins.pjx_page_loader.pjx_page_loader"}
    ),
    "builtins.pjx_page_loader.pjx_page_loader": frozenset({"pyjinhx._component"}),
}


def module_paths() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def module_name(path: Path) -> str:
    """Dotted name relative to the package root, e.g. ``reactive.keys``."""
    return ".".join(path.relative_to(PACKAGE_ROOT).with_suffix("").parts)


def internal_imports(path: Path) -> set[str]:
    """Every ``pyjinhx.*`` module name imported by ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, (
                f"{path.name} must use absolute imports, not relative ones"
            )
            names = [node.module or ""]
        else:
            continue
        found.update(n for n in names if n == "pyjinhx" or n.startswith("pyjinhx."))
    return found


def test_every_module_is_covered_by_the_declared_edge_table():
    """A new module must declare its edges here before it can be imported
    anywhere — otherwise the table silently stops being a whole-package view."""
    on_disk = {module_name(path) for path in module_paths()}
    assert on_disk == set(ALLOWED_INTERNAL_IMPORTS)


@pytest.mark.parametrize("path", module_paths(), ids=module_name)
def test_module_imports_only_declared_internal_modules(path: Path):
    allowed = ALLOWED_INTERNAL_IMPORTS[module_name(path)]
    unexpected = internal_imports(path) - allowed
    assert not unexpected, (
        f"{path.name} imports undeclared internal modules: {sorted(unexpected)}"
    )


def test_descriptor_imports_nothing_from_pyjinhx():
    assert internal_imports(PACKAGE_ROOT / "descriptor.py") == set()


def test_segments_imports_nothing_from_pyjinhx():
    assert internal_imports(PACKAGE_ROOT / "segments.py") == set()


def test_component_is_the_only_importer_of_class_descriptor():
    """The wiring seam (#271) is the one sanctioned reach upward. Anything else
    importing ClassDescriptor means the fact sheet is being rebuilt somewhere it
    should be read from the class instead."""
    importers = {
        module_name(path)
        for path in module_paths()
        if "pyjinhx.descriptor" in internal_imports(path)
    }
    assert importers == {"_component"}


def test_session_never_reaches_into_reactive():
    """session.py owns the per-request ContextVars; reactive/ imports them from
    here. The reverse edge would invert the spine."""
    imports = internal_imports(PACKAGE_ROOT / "session.py")
    assert not any(name.startswith("pyjinhx.reactive") for name in imports)
    assert imports <= {
        "pyjinhx.markers",
        "pyjinhx._component",
        "pyjinhx.segments",
        "pyjinhx.assets",
        "pyjinhx.config",
    }


def test_nothing_below_config_imports_config():
    """config is the top of the stack: it reads the spine, reactive/ and
    client/, and none of them may reach back up into it.

    integrations.fastapi is the one declared exception: it sits alongside
    config, not below it, and calls configure_pyjinhx/shutdown_pyjinhx to
    chain the app's lifespan — the two modules' mutual edges are each lazy
    (config imports integrations.fastapi inside setup(), see its own entry
    above) so the runtime cycle never actually executes at import time.

    session.py is the second exception, and a lazy one: request_scope() calls
    current_settings() inside its own body to seed a default session's Jinja
    environment. The edge never executes at import time, and
    test_session_only_imports_config_inside_a_function_body pins it there.
    """
    importers = {
        module_name(path)
        for path in module_paths()
        if "pyjinhx.config" in internal_imports(path)
    }
    assert importers == {"integrations.fastapi", "session"}


def test_nothing_imports_context():
    """context.py is a leaf consumer. The spine, reactive/ and client/ expose
    state through session.py's accessors; importing the facade back would make
    the view a dependency of the thing it views."""
    importers = {
        module_name(path)
        for path in module_paths()
        if "pyjinhx.context" in internal_imports(path)
    }
    assert importers == set()


def module_level_internal_imports(path: Path) -> set[str]:
    """Every ``pyjinhx.*`` module name imported at module scope by ``path`` —
    i.e. only the file's top-level statements, never descending into a
    function or class body. This is what distinguishes a real module-scope
    edge (which can create an import cycle) from the local-import escape
    hatch _component.py uses for rendering.py/session.py inside render()'s body."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        found.update(n for n in names if n == "pyjinhx" or n.startswith("pyjinhx."))
    return found


def test_component_only_imports_render_and_session_inside_a_method_body():
    """The docstring above and the ALLOWED_INTERNAL_IMPORTS comment on
    "component" both claim rendering.py/session.py are reached only from inside
    BaseComponent.render()'s method body, never at module scope — because
    rendering.py imports BaseComponent at import time, so a module-level edge
    back would be a real cycle (#643). Assert that claim directly: the whole
    file's edge table above passes even if the import moves to module scope,
    since it doesn't distinguish where in the file the import lives."""
    module_level = module_level_internal_imports(PACKAGE_ROOT / "_component.py")
    assert "pyjinhx.rendering" not in module_level
    assert "pyjinhx.session" not in module_level


def test_session_only_imports_config_inside_a_function_body():
    """request_scope() reads current_settings() to seed a default session's
    Jinja environment, but config sits above the render spine: a module-scope
    edge would invert the layering and, because config imports the spine at
    import time, would be a genuine cycle. The whole-file edge table can't see
    where in the file an import lives, so pin it here."""
    module_level = module_level_internal_imports(PACKAGE_ROOT / "session.py")
    assert "pyjinhx.config" not in module_level


def test_no_render_spine_module_declares_a_reactive_import():
    """FORBIDDEN per architecture-overview.md: anything in the render spine
    importing reactive/. pyjinhx/reactive/ doesn't exist yet (#288), so this
    guards the allowlist table itself — it must fail the moment someone adds
    a pyjinhx.reactive entry to any spine module's allowed set, before a
    single file under reactive/ is ever written."""
    for module in RENDER_SPINE_MODULES:
        allowed = ALLOWED_INTERNAL_IMPORTS.get(module, frozenset())
        reactive_edges = {
            name
            for name in allowed
            if name == "pyjinhx.reactive" or name.startswith("pyjinhx.reactive.")
        }
        assert not reactive_edges, (
            f"{module} declares forbidden reactive import(s): {sorted(reactive_edges)}"
        )


RENDER_SPINE_MODULES = (
    "_component",
    "descriptor",
    "markers",
    "rendering",
    "render_context",
    "root_attrs",
    "segments",
    "session",
)


@pytest.mark.parametrize("stem", RENDER_SPINE_MODULES)
def test_render_spine_modules_do_not_import_reactive_on_disk(stem: str):
    """Redundant with test_no_render_spine_module_declares_a_reactive_import
    while ALLOWED_INTERNAL_IMPORTS is the source of truth, but catches drift
    if a spine file imports pyjinhx.reactive directly without the allowlist
    table being updated to match (e.g. a bypass that skips declaring the
    edge)."""
    path = PACKAGE_ROOT / f"{stem}.py"
    reactive_imports = {
        name
        for name in internal_imports(path)
        if name == "pyjinhx.reactive" or name.startswith("pyjinhx.reactive.")
    }
    assert not reactive_imports, (
        f"{path.name} imports forbidden reactive module(s): {sorted(reactive_imports)}"
    )
