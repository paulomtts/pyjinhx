from pyjinhx import BaseComponent
from tests.ui.button import Button


class ButtonList(BaseComponent):
    id: str
    title: str
    buttons: list[Button]

