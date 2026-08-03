"""The todo example's FastAPI wiring: one app, four routes, no page shell.

Every route returns a component or a ReactiveResponse and lets the adapter turn
it into HTML — there is no HTMLResponse and no ctx= anywhere in this file,
because PjxScopeMiddleware opens the request scope and injects the app context
the components' load() methods read.
"""

from fastapi import FastAPI, Form, HTTPException
from starlette.requests import Request

from examples.todo import store
from examples.todo.components import App, ClearButton, Counter, ItemList, ItemRow, Total
from examples.todo.context import TodoAppContext
from pyjinhx import setup
from pyjinhx.reactive.response import ReactiveResponse
from pyjinhx.rendering import render
from pyjinhx.session import current_session

app = FastAPI()

setup(
    app,
    context_factory=lambda request: TodoAppContext(store=store),
    components_root="examples/todo/components",
)


@app.get("/")
def index():
    """The whole panel, assembled and loaded.

    App is a plain shell whose four fields are interpolated by name, so nothing
    populates them for us: a child assigned to a field is never mounted by the
    renderer, and an unloaded one would render as its defaults.
    """
    item_list = ItemList(id="list")
    item_list.load()
    remaining = Counter(id="counter")
    remaining.load()
    total_count = Total(id="total")
    total_count.load()
    clear_button = ClearButton(id="clear")
    clear_button.load()
    return App(
        id="app",
        item_list=item_list,
        remaining=remaining,
        total_count=total_count,
        clear_button=clear_button,
    )
