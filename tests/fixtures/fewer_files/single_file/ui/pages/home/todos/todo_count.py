from pydantic import computed_field

from tests.fixtures.fewer_files import domain
from tests.fixtures.fewer_files.domain import Keys, Tone
from tests.fixtures.fewer_files.reactive import AppReactive


class TodoCount(AppReactive, react={Keys.TODOS}):
    """How many todos are still open; reloads whenever one changes."""

    remaining: int = 0

    @classmethod
    def load(cls) -> "TodoCount":
        return cls(remaining=domain.remaining())

    @computed_field
    @property
    def noun(self) -> str:
        return domain.plural(self.remaining, "task")

    @computed_field
    @property
    def tone(self) -> Tone:
        return domain.tone_for(self.remaining)

    template = r"""
    <p id="{{ id }}" class="todo-count"><StatusDot tone="{{ tone.value }}"/> {{ remaining }} {{ noun }} left</p>
    {#css
    .todo-count { font-weight: 600; }
    #}
    """
