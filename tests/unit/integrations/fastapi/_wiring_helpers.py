"""Helpers shared by the split test files in this folder."""

from pathlib import Path

from pyjinhx.components.base import BaseComponent, ClassDescriptor
from pyjinhx.config import PjxSettings


class Greeting(BaseComponent):
    name: str = "world"


Greeting.__pjx_descriptor__ = ClassDescriptor(
    template_path=Path(__file__).parents[3]
    / "fixtures"
    / "templates"
    / "fastapi/pjx_integrations_greeting.html",
    slot_fields=frozenset(),
    children_field=None,
    css_paths=(),
    js_paths=(),
    strict=True,
    provenance={"template": Greeting},
)


def _settings(**kwargs) -> PjxSettings:
    return PjxSettings(**kwargs)
