from pydantic import Field

from pyjinhx import BaseComponent


class EmptyState(BaseComponent):
    image: str | BaseComponent = ""
    title: str | BaseComponent = ""
    description: str | BaseComponent = ""
    action: str | BaseComponent = ""
    actions: list[str | BaseComponent] = Field(default_factory=list)
