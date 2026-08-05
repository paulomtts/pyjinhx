from pyjinhx._component import AttrValue, BaseComponent


class PJXPromptDialog(BaseComponent):
    """The prompt shell and its label/button text; the question, initial value and open/close are driven by pjx.prompt(), not by fields here."""

    input_label: str = ""
    submit_label: str = "OK"
    cancel_label: str = "Cancel"
    class_name: AttrValue = ""
