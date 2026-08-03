"""Per-request context for the todo example."""

from dataclasses import dataclass
from typing import Any

from pyjinhx import AppContext


@dataclass(frozen=True)
class TodoAppContext(AppContext):
    store: Any
