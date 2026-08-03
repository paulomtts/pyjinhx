"""The todo example's FastAPI wiring: what each route puts on the wire."""

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
