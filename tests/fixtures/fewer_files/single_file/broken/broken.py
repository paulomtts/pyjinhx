from pyjinhx import BaseComponent


class BrokenNote(BaseComponent):
    """A template with a syntax error on a known line."""

    text: str = ""

    template = r"""
    <div class="note">
      <p>{{ text }}</p>
      {% if %}
    </div>
    """


class StrayLookup(BaseComponent):
    """A template that fails while rendering, on a known line."""

    template = r"""
    <div class="note">
      {{ nothing.here }}
    </div>
    """
