"""The pieces of a todo row, kept together in one module."""

from typing import Annotated

from pydantic import Field, computed_field, field_validator

from pyjinhx import BaseComponent, PjxKey, ReactiveComponent
from tests.fixtures.fewer_files import domain
from tests.fixtures.fewer_files.domain import (
    Keys,
    Todo,
    format_cents,
    normalise_currency,
)


class Money(BaseComponent):
    """An amount in cents, shown in its currency."""

    cents: int
    currency: str = "EUR"

    @field_validator("currency")
    @classmethod
    def _known_currency(cls, value: str) -> str:
        return normalise_currency(value)

    @computed_field
    @property
    def amount(self) -> str:
        return format_cents(self.cents, self.currency)

    @property
    def is_free(self) -> bool:
        return self.cents == 0

    @classmethod
    def of(cls, todo: Todo) -> "Money":
        return cls(cents=todo.cents)

    template = r"""
    <data class="money" value="{{ cents }}">{{ amount }}</data>
    """


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

    template = r"""
    <li class="todo-row todo-row--{{ state }}">
      <StatusDot tone="{{ 'calm' if done else 'busy' }}"/>
      <span class="todo-row__title">{{ title }}</span>
      <Money cents="{{ cents }}"/>
    </li>
    """


class TodoList(BaseComponent):
    """The first page of todos, as rows that each load themselves."""

    auto_id = False

    todo_ids: list[int] = Field(default_factory=list)

    @classmethod
    def build(cls, id: str) -> "TodoList":
        todos = domain.all_todos()[: domain.PAGE_SIZE]
        return cls(id=id, todo_ids=[todo.id for todo in todos])

    template = r"""
    <ul id="{{ id }}" class="todo-list">
      {% for todo_id in todo_ids %}<TodoRow todo_id="{{ todo_id }}"/>{% else %}<EmptyState message="All clear"/>{% endfor %}
    </ul>
    """
