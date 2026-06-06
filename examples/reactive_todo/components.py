from typing import ClassVar, Optional

from pyjinhx import BaseComponent, ReactiveComponent

from . import store


class TodoItem(BaseComponent):
    todo_id: int
    text: str
    done: bool = False


class TodoItemRow(ReactiveComponent):
    title: str = ""
    done: bool = False
    reacts_to: ClassVar[set[str]] = {"todo"}

    @classmethod
    def load(cls, key: str | int) -> "TodoItemRow":
        t = store.get(int(key))
        return cls(title=t.text, done=t.done)


class TodoList(BaseComponent):
    items: list[TodoItemRow] = []


class TodoCounter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "TodoCounter":
        return cls(remaining=store.remaining())


class TodoTotal(ReactiveComponent):
    total: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "TodoTotal":
        return cls(total=store.total())


class TodoClearButton(ReactiveComponent):
    completed: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "TodoClearButton":
        return cls(id="todo-clear", completed=store.completed())


class TodoApp(BaseComponent, base_layout=True):
    todo_list: Optional[TodoList] = None
    counter: Optional[TodoCounter] = None
    total: Optional[TodoTotal] = None
    clear_button: Optional[TodoClearButton] = None
