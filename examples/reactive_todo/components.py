from dataclasses import dataclass
from typing import Annotated, Any, Optional

from pyjinhx import BaseComponent, PjxContext, PjxKey, ReactiveComponent

from .keys import Keys


@dataclass(frozen=True)
class AppLoadContext:
    """Request-scoped access to the demo store module."""

    store: Any


def _store() -> Any:
    ctx = PjxContext.current()
    if isinstance(ctx, AppLoadContext):
        return ctx.store
    from . import store

    return store


class ItemRow(ReactiveComponent, react={Keys.TODOS}):
    todo_id: Annotated[int, PjxKey()]
    title: str = ""
    done: bool = False

    @classmethod
    def load(cls, todo_id: int | str) -> "ItemRow":
        store = _store()
        resolved_id = int(todo_id)
        todo = store.get(resolved_id)
        return cls(
            id=f"row-{resolved_id}",
            todo_id=resolved_id,
            title=todo.text,
            done=todo.done,
        )


class ItemList(ReactiveComponent, react={Keys.TODO_LIST}):
    items: list[ItemRow] = []

    @classmethod
    def load(cls) -> "ItemList":
        store = _store()
        return cls(
            id="list",
            items=[ItemRow.load(todo.id) for todo in store.all_todos()],
        )


class Counter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int = 0

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=_store().remaining())


class Total(ReactiveComponent, react={Keys.TODOS}):
    count: int = 0

    @classmethod
    def load(cls) -> "Total":
        return cls(count=_store().total())


class ClearButton(ReactiveComponent, react={Keys.TODOS}):
    completed: int = 0

    @classmethod
    def load(cls) -> "ClearButton":
        return cls(id="clear", completed=_store().completed())


class App(BaseComponent):
    item_list: Optional[ItemList] = None
    remaining: Optional[Counter] = None
    total_count: Optional[Total] = None
    clear_button: Optional[ClearButton] = None
