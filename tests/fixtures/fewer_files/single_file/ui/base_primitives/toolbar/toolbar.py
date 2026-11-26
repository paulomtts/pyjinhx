from pydantic import Field

from pyjinhx import BaseComponent
from tests.fixtures.fewer_files.domain import default_actions


class Toolbar(BaseComponent):
    """The page's action strip: one badge per action, then the two buttons."""

    title: str = "Actions"
    actions: list[str] = Field(default_factory=default_actions)

    template = r"""
    <Card title="{{ title }}">
      {% for action in actions %}<Badge id="action-{{ action }}" label="{{ action }}" variant="accent"/>{% endfor %}
      <Button label="Add" hx_post="/todos" attrs='{"hx-target": "#todo-list", "hx-swap": "beforeend"}'/>
      <Button label="Clear" kind="ghost"/>
    </Card>
    """
