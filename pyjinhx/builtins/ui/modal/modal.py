from pyjinhx import BaseComponent


class Modal(BaseComponent):
    title: str | BaseComponent = ""
    header: str | BaseComponent = ""  # replaces title when set
    body: str | BaseComponent = ""
    footer: str | BaseComponent = ""
