from dataclasses import dataclass
from typing import Annotated, ClassVar, Optional

from pyjinhx import BaseComponent, PjxContext, PjxKey, ReactiveComponent

from .keys import Keys


@dataclass(frozen=True)
class AppLoadContext:
    """Request-scoped access to the demo store module."""

    store: object


def _store():
    ctx = PjxContext.current()
    if isinstance(ctx, AppLoadContext):
        return ctx.store
    from . import store

    return store


class ItemRow(ReactiveComponent):
    todo_id: Annotated[int, PjxKey()]
    title: str = ""
    done: bool = False
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}
    loading: ClassVar[str] = "skeleton"

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


class ItemList(ReactiveComponent):
    items: list[ItemRow] = []
    reacts_to: ClassVar[set[str]] = {Keys.TODO_LIST}

    @classmethod
    def load(cls) -> "ItemList":
        store = _store()
        return cls(
            id="list",
            items=[ItemRow.load(todo.id) for todo in store.all_todos()],
        )


class Counter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=_store().remaining())


class Total(ReactiveComponent):
    count: int = 0
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}

    @classmethod
    def load(cls) -> "Total":
        return cls(count=_store().total())


class ClearButton(ReactiveComponent):
    completed: int = 0
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}
    loading: ClassVar[str] = "spinner"

    @classmethod
    def load(cls) -> "ClearButton":
        return cls(id="clear", completed=_store().completed())


class App(BaseComponent):
    item_list: Optional[ItemList] = None
    remaining: Optional[Counter] = None
    total_count: Optional[Total] = None
    clear_button: Optional[ClearButton] = None
