from dataclasses import dataclass
from typing import ClassVar, Optional

from pyjinhx import BaseComponent, LoadContext, ReactiveComponent

from .keys import Keys


@dataclass(frozen=True)
class AppLoadContext:
    """Request-scoped access to the demo store module."""

    store: object


def _store():
    ctx = LoadContext.current()
    if isinstance(ctx, AppLoadContext):
        return ctx.store
    from . import store

    return store


class ItemRow(ReactiveComponent):
    title: str = ""
    done: bool = False
    reacts_to: ClassVar[set[str]] = {Keys.TODO}

    @classmethod
    def load(cls, key: str | int) -> "ItemRow":
        store = _store()
        todo = store.get(int(key))
        return cls(id=f"row-{key}", title=todo.text, done=todo.done)


class ItemList(ReactiveComponent):
    items: list[ItemRow] = []
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}

    @classmethod
    def load(cls) -> "ItemList":
        store = _store()
        return cls(
            id="list",
            items=[ItemRow.load(t.id) for t in store.all_todos()],
        )


class Counter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=_store().remaining())


class Total(ReactiveComponent):
    total: int = 0
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}

    @classmethod
    def load(cls) -> "Total":
        return cls(total=_store().total())


class ClearButton(ReactiveComponent):
    completed: int = 0
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}

    @classmethod
    def load(cls) -> "ClearButton":
        return cls(id="clear", completed=_store().completed())


class App(BaseComponent):
    item_list: Optional[ItemList] = None
    remaining: Optional[Counter] = None
    total_count: Optional[Total] = None
    clear_button: Optional[ClearButton] = None
