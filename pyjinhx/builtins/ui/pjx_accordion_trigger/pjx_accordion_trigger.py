from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, Slot
from pyjinhx.builtins.ui.pjx_icon import PJXIcon


def _default_chevron() -> PJXIcon:
    return PJXIcon(name="chevron-right", class_name="pjx-accordion__chevron")


class PJXAccordionTrigger(BaseComponent):
    """The <summary> row that toggles its parent PJXAccordion, with the chevron affordance."""

    disabled: bool = False
    class_name: AttrValue = ""
    content: Slot = ""
    # Composed in Python, not as a <PJXIcon/> literal in the template: a tag
    # literal only resolves once build_registry() has run, so the chevron
    # vanished into passthrough markup in any render path that never called
    # setup() — the docs demo build among them (#693). A component-typed field
    # is a slot by convention and renders through the slot-token path instead.
    chevron: PJXIcon = Field(default_factory=_default_chevron)
