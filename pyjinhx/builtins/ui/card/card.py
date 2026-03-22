from pyjinhx import BaseComponent


class Card(BaseComponent):
    title: str | BaseComponent = ""
    header: str | BaseComponent = ""
    body: str | BaseComponent = ""
    footer: str | BaseComponent = ""
