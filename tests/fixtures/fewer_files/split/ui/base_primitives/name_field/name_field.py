from pyjinhx import BaseComponent


class NameField(BaseComponent):
    """A form's required name input and the error under it.

    An answer swaps it out of band (``oob``) with the posted value, so the
    error changes without touching the rest of the form. Each form subclasses
    it with its own input id and label.
    """

    auto_id = False

    input_id: str = ""
    label: str = ""
    value: str = ""
    error: str = ""
    oob: bool = False
