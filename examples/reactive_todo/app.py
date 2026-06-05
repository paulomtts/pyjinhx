from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

from pyjinhx import Renderer

from . import store
from .components import (
    TodoApp,
    TodoClearButton,
    TodoCounter,
    TodoItem,
    TodoList,
    TodoTotal,
)

# Resolve templates relative to the repo root regardless of the process CWD.
Renderer.set_default_environment(Path(__file__).resolve().parents[2])

app = FastAPI(title="pyjinhx reactive todo demo")


def _item(todo: store.Todo) -> TodoItem:
    return TodoItem(
        id=f"todo-{todo.id}", todo_id=todo.id, text=todo.text, done=todo.done
    )


def _list() -> TodoList:
    return TodoList(id="todo-list", items=[_item(t) for t in store.all_todos()])


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
    # The primary (the new row) isn't itself reactive, so we name what we dirtied.
    return str(_item(todo).render(dirtied={"todos"}, mounted=request))


@app.post("/todos/{todo_id}/toggle", response_class=HTMLResponse)
def toggle(request: Request, todo_id: int) -> str:
    todo = store.toggle(todo_id)
    return str(_item(todo).render(dirtied={"todos"}, mounted=request))


@app.post("/todos/clear-completed", response_class=HTMLResponse)
def clear_completed(request: Request) -> str:
    store.clear_completed()
    return str(_list().render(dirtied={"todos"}, mounted=request))
