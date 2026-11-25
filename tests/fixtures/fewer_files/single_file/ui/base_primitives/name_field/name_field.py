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

    template = r"""
    <div id="{{ id }}" class="name-field"{% if oob %} hx-swap-oob="outerHTML"{% endif %}>
      <label for="{{ input_id }}">{{ label }}</label>
      <input id="{{ input_id }}" name="name" value="{{ value }}"{% if error %} aria-invalid="true"{% endif %}>
      {% if error %}<p class="field-error" role="alert">{{ error }}</p>{% endif %}
    </div>
    """
