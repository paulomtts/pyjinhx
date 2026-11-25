from pydantic import Field

from pyjinhx import BaseComponent
from tests.fixtures.fewer_files import domain


class TodoList(BaseComponent):
    """The first page of todos, as rows that each load themselves."""

    auto_id = False

    todo_ids: list[int] = Field(default_factory=list)

    @classmethod
    def build(cls, id: str) -> "TodoList":
        todos = domain.all_todos()[: domain.PAGE_SIZE]
        return cls(id=id, todo_ids=[todo.id for todo in todos])
