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
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "TodoCounter":
        # No id needed: it defaults to the kebab class name -> "todo-counter".
        return cls(remaining=store.remaining())


class TodoTotal(ReactiveComponent):
    total: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "TodoTotal":
        # Defaults to "todo-total".
        return cls(total=store.total())


class TodoClearButton(ReactiveComponent):
    completed: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "TodoClearButton":
        # Escape hatch: pin an explicit id (here a shorter one than the default
        # "todo-clear-button"). Required when you mount multiple instances of a type.
        return cls(id="todo-clear", completed=store.completed())


class TodoApp(BaseComponent, base_layout=True):
    todo_list: Optional[TodoList] = None
    counter: Optional[TodoCounter] = None
    total: Optional[TodoTotal] = None
    clear_button: Optional[TodoClearButton] = None
