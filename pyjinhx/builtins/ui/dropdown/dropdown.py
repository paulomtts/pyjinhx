from pyjinhx import BaseComponent


class Dropdown(BaseComponent):
    trigger: str | BaseComponent = ""
    menu: str | BaseComponent = ""
