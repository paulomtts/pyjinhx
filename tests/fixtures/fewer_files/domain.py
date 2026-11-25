"""The app every fewer-files shape renders: its store, keys, enums and helpers.

Plain Python with no components in it, so all three shapes import the same
values — a header names them by dotted path, a class imports them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pyjinhx import MutationKey, mutates

PAGE_SIZE = 3
CURRENCIES = ("EUR", "USD", "BRL")


class Keys(MutationKey):
    TODOS = "todos"


class Tone(StrEnum):
    CALM = "calm"
    BUSY = "busy"
    LATE = "late"


@dataclass
class Todo:
    id: int
    title: str
    cents: int
    done: bool = False


_todos: dict[int, Todo] = {}


def reset() -> None:
    """Back to the three seeded todos."""
    _todos.clear()
    for number, (title, cents) in enumerate(
        [("Write the brief", 1250), ("Book the venue", 98000), ("Order <snacks>", 0)],
        start=1,
    ):
        _todos[number] = Todo(id=number, title=title, cents=cents)


def all_todos() -> list[Todo]:
    return list(_todos.values())


def get(todo_id: int) -> Todo:
    return _todos[todo_id]


def remaining() -> int:
    return sum(not todo.done for todo in _todos.values())


@mutates(Keys.TODOS)
def toggle(todo_id: int) -> Todo:
    _todos[todo_id].done = not _todos[todo_id].done
    return _todos[todo_id]


def plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def normalise_currency(code: str) -> str:
    """``code`` upper-cased; raises ``ValueError`` for one the app does not bill in."""
    code = code.strip().upper()
    if code not in CURRENCIES:
        raise ValueError(f"unknown currency {code!r}")
    return code


def format_cents(cents: int, currency: str) -> str:
    return f"{currency} {cents // 100:,}.{cents % 100:02d}"


def tone_for(count: int) -> Tone:
    if count == 0:
        return Tone.CALM
    return Tone.BUSY if count < PAGE_SIZE else Tone.LATE


def default_actions() -> list[str]:
    return ["add", "clear"]


reset()
