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
    TodoLoadContext,
    TodoTotal,
)
from pyjinhx import Registry, Renderer

Renderer.set_default_environment(Path(__file__).resolve().parents[2])

app = FastAPI(title="pyjinhx reactive todo demo")


def _item(todo: store.Todo) -> TodoItem:
    return TodoItem(
        id=f"todo-{todo.id}", todo_id=todo.id, text=todo.text, done=todo.done
    )


def _list() -> TodoList:
    return TodoList(
        id="todo-list",
        items=[TodoItemRow.load(t.id) for t in store.all_todos()],
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    with Registry.request_scope(load_context=TodoLoadContext(store=store)):
        return TodoApp(
            id="todo-app",
            todo_list=_list(),
            counter=TodoCounter.load(),
            total=TodoTotal.load(),
            clear_button=TodoClearButton.load(),
        ).render()


@app.post("/todos", response_class=HTMLResponse)
def add(request: Request, text: str = Form(...)) -> str:
    with Registry.request_scope(load_context=TodoLoadContext(store=store)):
        store.add(text)
        return TodoItemRow.render(store.all_todos()[-1].id, mounted=request)


@app.post("/rows/{todo_id}/toggle", response_class=HTMLResponse)
def toggle_row(request: Request, todo_id: int) -> str:
    with Registry.request_scope(load_context=TodoLoadContext(store=store)):
        store.toggle(todo_id)
        return TodoItemRow.render(todo_id, mounted=request)


@app.post("/todos/{todo_id}/toggle", response_class=HTMLResponse)
def toggle(request: Request, todo_id: int) -> str:
    with Registry.request_scope(load_context=TodoLoadContext(store=store)):
        todo = store.toggle(todo_id)
        return _item(todo).render(mounted=request)


@app.post("/todos/clear-completed", response_class=HTMLResponse)
def clear_completed(request: Request) -> str:
    with Registry.request_scope(load_context=TodoLoadContext(store=store)):
        store.clear_completed()
        return _list().render(mounted=request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
