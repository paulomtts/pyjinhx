from dataclasses import dataclass
from typing import ClassVar, Optional

from pyjinhx import BaseComponent, ReactiveComponent
from pyjinhx.reactive.context import get_load_context

from .keys import Keys


@dataclass(frozen=True)
class TodoLoadContext:
    """Request-scoped access to the demo store module."""

    store: object


def _store():
    ctx = get_load_context()
    if isinstance(ctx, TodoLoadContext):
        return ctx.store
    from . import store

    return store


class TodoItem(BaseComponent):
    todo_id: int
    text: str
    done: bool = False


class TodoItemRow(ReactiveComponent):
    title: str = ""
    done: bool = False
    reacts_to: ClassVar[set[str]] = {Keys.TODO}
    load_reads: ClassVar[set[str]] = {Keys.TODO}

    @classmethod
    def load(cls, key: str | int) -> "TodoItemRow":
        store = _store()
        todo = store.get(int(key))
        return cls(id=f"todo-row-{key}", title=todo.text, done=todo.done)


class TodoList(BaseComponent):
    items: list[TodoItemRow] = []


class TodoCounter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}
    load_reads: ClassVar[set[str]] = {Keys.TODOS}

    @classmethod
    def load(cls) -> "TodoCounter":
        return cls(remaining=_store().remaining())


class TodoTotal(ReactiveComponent):
    total: int = 0
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}
    load_reads: ClassVar[set[str]] = {Keys.TODOS}

    @classmethod
    def load(cls) -> "TodoTotal":
        return cls(total=_store().total())


class TodoClearButton(ReactiveComponent):
    completed: int = 0
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}
    load_reads: ClassVar[set[str]] = {Keys.TODOS}

    @classmethod
    def load(cls) -> "TodoClearButton":
        return cls(id="todo-clear", completed=_store().completed())


class TodoApp(BaseComponent):
    todo_list: Optional[TodoList] = None
    counter: Optional[TodoCounter] = None
    total: Optional[TodoTotal] = None
    clear_button: Optional[TodoClearButton] = None
