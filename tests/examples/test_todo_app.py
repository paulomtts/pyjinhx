"""The todo example's FastAPI wiring: what each route puts on the wire."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from examples.todo import store as todo_store
from examples.todo.app import app


@pytest.fixture
def client():
    """A TestClient over the example app, lifespan entered so setup() applies."""
    with TestClient(app) as test_client:
        yield test_client


class TestIndex:
    def test_serves_the_panel_shell(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert "bar__title" in response.text
        assert 'class="composer"' in response.text

    def test_renders_every_seeded_todo(self, client):
        html = client.get("/").text

        assert "Write the docs" in html
        assert "Ship reactivity" in html
        assert "Touch grass" in html

    def test_the_context_factory_reaches_the_children(self, client):
        """The counters only have numbers if load() saw a TodoAppContext."""
        html = client.get("/").text

        assert "3" in html
        assert 'id="list"' in html

    def test_children_are_tag_nested_and_id_stamped(self, client):
        """No route code stamps these ids — _fill_children applies the tag attrs."""
        template_src = Path("examples/todo/components/app/app.pjx").read_text()
        assert "<ItemList" in template_src
        assert "<Counter" in template_src
        assert "<Total" in template_src
        assert "<ClearButton" in template_src

        html = client.get("/").text

        assert 'data-pjx-id="counter"' in html
        assert 'data-pjx-id="total"' in html
        assert 'data-pjx-id="clear"' in html
        assert 'data-pjx-id="list"' in html
        assert "3 left" in html
        assert "3 total" in html
        assert "Clear completed (0)" in html


class TestAdd:
    def test_returns_the_new_row_as_the_primary_fragment(self, client):
        response = client.post("/todos", data={"text": "buy milk"})

        assert response.status_code == 200
        assert "buy milk" in response.text
        assert 'hx-post="/rows/4/toggle"' in response.text

    def test_the_todo_lands_in_the_store(self, client):
        client.post("/todos", data={"text": "buy milk"})

        assert [todo.text for todo in todo_store.all_todos()][-1] == "buy milk"
        assert todo_store.total() == 4

    def test_a_follow_up_page_load_shows_it(self, client):
        client.post("/todos", data={"text": "buy milk"})

        assert "buy milk" in client.get("/").text

    def test_missing_text_is_a_422(self, client):
        assert client.post("/todos", data={}).status_code == 422


class TestToggle:
    def test_flips_the_todo_in_the_store(self, client):
        todo_id = todo_store.all_todos()[0].id

        response = client.post(f"/rows/{todo_id}/toggle")

        assert response.status_code == 200
        assert todo_store.get(todo_id).done is True

    def test_returns_the_row_in_its_new_state(self, client):
        todo_id = todo_store.all_todos()[0].id

        html = client.post(f"/rows/{todo_id}/toggle").text

        assert 'class="todo done"' in html
        assert f'data-pjx-id="row-{todo_id}"' in html

    def test_toggling_twice_returns_to_open(self, client):
        todo_id = todo_store.all_todos()[0].id

        client.post(f"/rows/{todo_id}/toggle")
        client.post(f"/rows/{todo_id}/toggle")

        assert todo_store.get(todo_id).done is False

    def test_an_unknown_id_is_a_404(self, client):
        assert client.post("/rows/9999/toggle").status_code == 404


class TestClearCompleted:
    def test_drops_completed_and_keeps_the_rest(self, client):
        todos = todo_store.all_todos()
        client.post(f"/rows/{todos[0].id}/toggle")

        response = client.post("/todos/clear-completed")

        assert response.status_code == 200
        assert [todo.text for todo in todo_store.all_todos()] == [
            "Ship reactivity",
            "Touch grass",
        ]

    def test_an_oob_only_response_tells_htmx_not_to_swap_the_primary(self, client):
        client.post(f"/rows/{todo_store.all_todos()[0].id}/toggle")

        response = client.post("/todos/clear-completed")

        assert response.headers["hx-reswap"] == "none"

    def test_nothing_completed_is_a_no_op(self, client):
        client.post("/todos/clear-completed")

        assert todo_store.total() == 3


class TestSourceGuard:
    def test_the_example_names_no_removed_response_api(self):
        """The example is the migration reference: nothing v1-shaped may survive in it."""
        source = Path("examples/todo/app.py").read_text()

        assert "ReactiveResponse" not in source
        assert ".render()" not in source

    def test_no_route_takes_an_unused_request_argument(self):
        """Routes return components; none of them needs the Request object."""
        source = Path("examples/todo/app.py").read_text()

        assert "Request" not in source

    def test_the_reactivity_doc_names_no_removed_response_api(self):
        """docs/reactivity.md must describe compose(), not the deleted class."""
        doc = Path("docs/reactivity.md").read_text()

        assert "ReactiveResponse" not in doc
        assert "appends OOB swaps" not in doc

    def test_the_htmx_doc_names_no_removed_response_api(self):
        """docs/integrations/htmx.md must describe native 3xx translation."""
        doc = Path("docs/integrations/htmx.md").read_text()

        assert "ReactiveResponse" not in doc
        assert "HX-Redirect" in doc
