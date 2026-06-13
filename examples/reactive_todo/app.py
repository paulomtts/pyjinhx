from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from examples.reactive_todo import store
from examples.reactive_todo.components import (
    App,
    AppLoadContext,
    ClearButton,
    Counter,
    ItemList,
    ItemRow,
    Total,
)
from pyjinhx import PjxSettings, Renderer, setup

Renderer.set_default_environment(Path(__file__).resolve().parents[2])

app = FastAPI(title="pyjinhx reactive todo demo")
setup(
    app,
    settings=PjxSettings.from_env(),
    context_factory=lambda _request: AppLoadContext(store=store),
)


def _demo_latency() -> float:
    return float(os.environ.get("PJX_DEMO_LATENCY", "0.5"))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return App(
        id="app",
        item_list=ItemList.load(),
        remaining=Counter.load(),
        total_count=Total.load(),
        clear_button=ClearButton.load(),
    ).render()


@app.post("/todos", response_class=HTMLResponse)
def add(text: str = Form(...)) -> str:
    store.add(text)
    return ItemRow.render(store.all_todos()[-1].id)


@app.post("/rows/{todo_id}/toggle", response_class=HTMLResponse)
def toggle_row(todo_id: int) -> str:
    store.toggle(todo_id)
    time.sleep(_demo_latency())
    return ItemRow.render(todo_id)


@app.post("/todos/clear-completed", response_class=HTMLResponse)
def clear_completed() -> str:
    store.clear_completed()
    time.sleep(_demo_latency())
    return ItemList.render()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
