from examples.todo.components.clear_button import ClearButton
from examples.todo.components.counter import Counter
from examples.todo.components.item_list import ItemList
from examples.todo.components.total import Total
from pyjinhx import BaseComponent


class App(BaseComponent):
    """The todo panel: a plain shell that composes the reactive pieces.

    Renders a fragment, not a document — the page shell (doctype, head, the
    htmx script tag) is the app wiring's job, since a component template must
    render exactly one root element.
    """

    item_list: ItemList | None = None
    remaining: Counter | None = None
    total_count: Total | None = None
    clear_button: ClearButton | None = None
