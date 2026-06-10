from pyjinhx import BaseComponent


class LazyPanel(BaseComponent):
    url: str
    trigger: str = "revealed"
    swap: str = "outerHTML"
    content: str | BaseComponent = ""
