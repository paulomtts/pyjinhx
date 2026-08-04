from typing import Literal

from pydantic import Field, model_validator

from pyjinhx.builtins.pjx_region_loader import PJXRegionLoader
from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXButton(BaseComponent):
    """A themeable button whose label is a freeform slot.

    ``loading`` both disables the button and overlays a ``PJXRegionLoader``,
    so an in-flight request cannot be fired twice from the same control.
    """

    variant: str = "default"
    block: bool = False
    loading: bool = False
    disabled: bool = False
    type: Literal["button", "submit", "reset"] = "button"
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
    # Composed in Python rather than as a <PJXRegionLoader/> tag literal: a
    # literal only resolves once build_registry() has run, so the spinner was
    # emitted as raw tag text in any render path that never called setup()
    # (#693). The template only interpolates this when ``loading`` is set.
    loader: PJXRegionLoader = Field(default_factory=PJXRegionLoader)

    @model_validator(mode="after")
    def _pin_loader_id(self) -> "PJXButton":
        """Keep the overlay's id derived from the button's, as the tag literal did."""
        expected = f"{self.id}-loader"
        if self.loader.id != expected:
            self.loader.id = expected
        return self
