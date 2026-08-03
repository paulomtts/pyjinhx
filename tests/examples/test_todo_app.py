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
