"""Tiny in-memory todo store for the reactive demo."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count

_ids = count(1)
_todos: dict[int, "Todo"] = {}


@dataclass
class Todo:
    id: int
    text: str
    done: bool = False


def reset() -> None:
    global _todos, _ids
    _todos = {}
    _ids = count(1)
    for text in ("Write the docs", "Ship reactivity", "Touch grass"):
        add(text)


def add(text: str) -> Todo:
    todo = Todo(id=next(_ids), text=text)
    _todos[todo.id] = todo
    return todo


def toggle(todo_id: int) -> Todo:
    _todos[todo_id].done = not _todos[todo_id].done
    return _todos[todo_id]


def clear_completed() -> None:
    for todo_id in [tid for tid, t in _todos.items() if t.done]:
        del _todos[todo_id]


def all_todos() -> list[Todo]:
    return list(_todos.values())


def total() -> int:
    return len(_todos)


def remaining() -> int:
    return sum(1 for t in _todos.values() if not t.done)


def completed() -> int:
    return sum(1 for t in _todos.values() if t.done)


reset()
