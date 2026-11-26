from typing import Annotated

from pydantic import computed_field

from pyjinhx import PjxKey, ReactiveComponent
from tests.fixtures.fewer_files import domain
from tests.fixtures.fewer_files.domain import Keys, Todo


class TodoRow(ReactiveComponent, react={Keys.TODOS}):
    """One todo, keyed by its id so each row reloads on its own."""

    todo_id: Annotated[int, PjxKey()]
    title: str = ""
    cents: int = 0
    done: bool = False

    @classmethod
    def from_todo(cls, todo: Todo) -> "TodoRow":
        return cls(
            id=f"todo-{todo.id}",
            todo_id=todo.id,
            title=todo.title,
            cents=todo.cents,
            done=todo.done,
        )

    @classmethod
    def load(cls, todo_id: int) -> "TodoRow":
        return cls.from_todo(domain.get(todo_id))

    @computed_field
    @property
    def state(self) -> str:
        return "done" if self.done else "open"
