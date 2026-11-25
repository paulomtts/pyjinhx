from pydantic import computed_field

from pyjinhx import BaseComponent, Slot
from tests.fixtures.fewer_files import domain
from tests.fixtures.fewer_files.split.ui.base_primitives.badge.badge import Badge
from tests.fixtures.fewer_files.split.ui.pages.home.todos.todo_list.todo_list import (
    TodoList,
)

ARCHIVE_ICON = '<svg class="icon" viewBox="0 0 16 16"><path d="M1 3h14"/></svg>'


class TodoPage(BaseComponent):
    """The todos page: every component of the app, composed by tag."""

    title: str
    project: str
    currency: str = "EUR"
    badge: Slot = ""
    todo_list: Slot = ""
    # Plain strings, not slots: they travel through a tag attribute, which
    # escapes them on the way out and decodes them on the way in, so the
    # child's own Slot field receives the markup intact.
    summary: str = ""
    archive_icon: str = ARCHIVE_ICON

    @classmethod
    def build(cls, project: str) -> "TodoPage":
        return cls(
            id="todo-page",
            title="Todos",
            project=project,
            badge=Badge(id="project-badge", label=project, variant="accent"),
            summary=f"<em>{domain.remaining()} open</em>",
            todo_list=TodoList.build(id="todo-list"),
        )

    @computed_field
    @property
    def total_cents(self) -> int:
        return sum(todo.cents for todo in domain.all_todos())
