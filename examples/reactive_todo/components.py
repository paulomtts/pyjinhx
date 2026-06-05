from typing import ClassVar, Optional

from pyjinhx import BaseComponent, ReactiveComponent

from . import store


class TodoItem(BaseComponent):
    todo_id: int
    text: str
    done: bool = False


class TodoList(BaseComponent):
    items: list[TodoItem] = []


class TodoCounter(ReactiveComponent):
    remaining: int = 0
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "TodoCounter":
        return cls(id="todo-counter", remaining=store.remaining())


class TodoTotal(ReactiveComponent):
    total: int = 0
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "TodoTotal":
        return cls(id="todo-total", total=store.total())


class TodoClearButton(ReactiveComponent):
    completed: int = 0
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "TodoClearButton":
        return cls(id="todo-clear", completed=store.completed())


class TodoApp(BaseComponent, base_layout=True):
    todo_list: Optional[TodoList] = None
    counter: Optional[TodoCounter] = None
    total: Optional[TodoTotal] = None
    clear_button: Optional[TodoClearButton] = None
