from pydantic import Field

from pyjinhx import BaseComponent
from tests.fixtures.fewer_files.domain import default_actions


class Toolbar(BaseComponent):
    """The page's action strip: one badge per action, then the two buttons."""

    title: str = "Actions"
    actions: list[str] = Field(default_factory=default_actions)
