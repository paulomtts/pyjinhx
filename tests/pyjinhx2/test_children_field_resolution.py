"""Which declared field receives a PascalCase tag's body content (#369).

Field selection only: nothing here renders, mounts a tag, or splices content.
"""

from typing import Annotated, ClassVar

import pytest

from pyjinhx2.component import (
    BaseComponent,
    Children,
    PjxSlot,
    Slot,
    _resolve_children_field,
    _resolve_class_descriptor,
)


class TestNoTarget:
    def test_no_slot_fields_resolves_to_none(self):
        class Plain(BaseComponent):
            title: str = ""

        assert Plain.__pjx_descriptor__.children_field is None
