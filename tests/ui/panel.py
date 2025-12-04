from pyjinhx import BaseComponent
from tests.ui.button import Button


class Panel(BaseComponent):
    id: str
    title: str
    sections: dict[str, Button | str]

