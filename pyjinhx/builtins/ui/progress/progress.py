from pyjinhx import BaseComponent


class Progress(BaseComponent):
    value: float | None = None
    max: float = 100
    label: str = ""
