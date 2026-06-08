from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

from examples.reactive_todo import store
from examples.reactive_todo.invalidation import configure_load_cache, shutdown_load_cache
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
from pyjinhx import Registry, Renderer, client_backend_from_request

Renderer.set_default_environment(Path(__file__).resolve().parents[2])


@asynccontextmanager
async def lifespan(_application: FastAPI):
    configure_load_cache()
    yield
    shutdown_load_cache()


app = FastAPI(title="pyjinhx reactive todo demo", lifespan=lifespan)


class RegistryScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        with Registry.request_scope(
            load_context=TodoLoadContext(store=store),
            client_backend=client_backend_from_request(request),
        ):
            return await call_next(request)


app.add_middleware(RegistryScopeMiddleware)


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
    return TodoApp(
        id="todo-app",
        todo_list=_list(),
        counter=TodoCounter.load(),
        total=TodoTotal.load(),
        clear_button=TodoClearButton.load(),
    ).render()


@app.post("/todos", response_class=HTMLResponse)
def add(text: str = Form(...)) -> str:
    store.add(text)
    return TodoItemRow.render(store.all_todos()[-1].id)


@app.post("/rows/{todo_id}/toggle", response_class=HTMLResponse)
def toggle_row(todo_id: int) -> str:
    store.toggle(todo_id)
    return TodoItemRow.render(todo_id)


@app.post("/todos/{todo_id}/toggle", response_class=HTMLResponse)
def toggle(todo_id: int) -> str:
    todo = store.toggle(todo_id)
    return _item(todo).render()


@app.post("/todos/clear-completed", response_class=HTMLResponse)
def clear_completed() -> str:
    store.clear_completed()
    return _list().render()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
