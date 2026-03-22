from pyjinhx import BaseComponent


class EmptyState(BaseComponent):
    title: str | BaseComponent = ""
    description: str | BaseComponent = ""
    action: str | BaseComponent = ""
