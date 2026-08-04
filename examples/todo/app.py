"""The todo example's FastAPI wiring: one app, four routes, no page shell.

Every route returns a component and lets the adapter turn it into HTML — there
is no HTMLResponse and no ctx= anywhere in this file, because PjxScopeMiddleware
opens the request scope and injects the app context the components' load()
methods read.
"""

from fastapi import FastAPI, Form, HTTPException

from examples.todo import store
from examples.todo.components import App, ItemRow
from examples.todo.context import TodoAppContext
from pyjinhx import setup

app = FastAPI()

setup(
    app,
    context_factory=lambda request: TodoAppContext(store=store),
    components_root="examples/todo/components",
)


@app.get("/")
def index():
    """The whole panel, assembled by the renderer.

    App nests its four children as tags, so _fill_children builds each one
    through its cache-routed load() factory and applies the tag's id attr —
    nothing here loads or stamps anything by hand.
    """
    return App(id="app")


@app.post("/todos")
def add_todo(text: str = Form(...)):
    """Add one todo and return its row; the counters ride along out of band.

    The primary fragment is the row alone because the composer form targets
    #list with hx-swap="beforeend". The counters refresh because store.add's
    @mutates dirtied their keys for this request, not because this route asked
    for them.
    """
    todo = store.add(text)
    return ItemRow(todo_id=todo.id, id=f"row-{todo.id}")


@app.post("/rows/{todo_id}/toggle")
def toggle_todo(todo_id: int):
    """Flip one todo and return its row.

    store.toggle raises KeyError on an id it has never seen — a stale row in a
    long-open tab is a client mistake, not a server fault, so it becomes a 404
    rather than a 500. Every mounted region whose keys store.toggle's @mutates
    dirtied is swapped out of band alongside the row.
    """
    try:
        store.toggle(todo_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no todo {todo_id}") from None
    return ItemRow(todo_id=todo_id, id=f"row-{todo_id}")


@app.post("/todos/clear-completed")
def clear_completed():
    """Delete every completed todo; the page updates entirely out of band.

    Returning None means there is no primary fragment — the clear button has
    nothing of its own to swap in. The response is the OOB fan-out implied by
    the keys store.clear_completed's @mutates dirtied, plus the HX-Reswap: none
    an empty primary carries.
    """
    store.clear_completed()
