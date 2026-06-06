from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

from examples.reactive_todo import store
from examples.reactive_todo.components import (
    TodoApp,
    TodoClearButton,
    TodoCounter,
    TodoItem,
    TodoItemRow,
    TodoList,
    TodoTotal,
)
from pyjinhx import Renderer

# Resolve templates relative to the repo root regardless of the process CWD.
Renderer.set_default_environment(Path(__file__).resolve().parents[2])

app = FastAPI(title="pyjinhx reactive todo demo")


def _item(todo: store.Todo) -> TodoItem:
    return TodoItem(
        id=f"todo-{todo.id}", todo_id=todo.id, text=todo.text, done=todo.done
    )


def _list() -> TodoList:
    # Each row is an instance-keyed reactive region (id "todo-item-row-<id>"), so a
    # single-todo mutation can swap just that row out-of-band.
    return TodoList(
        id="todo-list",
        items=[TodoItemRow.load(t.id) for t in store.all_todos()],
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return str(
        TodoApp(
            id="todo-app",
            todo_list=_list(),
            counter=TodoCounter.load(),
            total=TodoTotal.load(),
            clear_button=TodoClearButton.load(),
        ).render()
    )


@app.post("/todos", response_class=HTMLResponse)
def add(request: Request, text: str = Form(...)) -> str:
    todo = store.add(text)
    # render() auto-loads the new row by its key (no manual load()); the new row is the
    # primary, and dirtying the collection-tier "todos" updates counter/total/clear OOB.
    return TodoItemRow.render(todo.id, dirtied={"todos"}, mounted=request)


@app.post("/rows/{todo_id}/toggle", response_class=HTMLResponse)
def toggle_row(request: Request, todo_id: int) -> str:
    store.toggle(todo_id)
    # render(key, ...) loads this row itself. Two-tier dirtied: "todo:<id>" swaps just
    # this row; "todos" updates the collection-tier regions (counter, total, clear).
    return TodoItemRow.render(
        todo_id, dirtied={f"todo:{todo_id}", "todos"}, mounted=request
    )


@app.post("/todos/{todo_id}/toggle", response_class=HTMLResponse)
def toggle(request: Request, todo_id: int) -> str:
    todo = store.toggle(todo_id)
    return str(_item(todo).render(dirtied={"todos"}, mounted=request))


@app.post("/todos/clear-completed", response_class=HTMLResponse)
def clear_completed(request: Request) -> str:
    store.clear_completed()
    return str(_list().render(dirtied={"todos"}, mounted=request))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
