import pytest
from fastapi.testclient import TestClient

from examples.reactive_todo.app import app


@pytest.fixture(autouse=True)
def _no_demo_latency(monkeypatch):
    monkeypatch.setenv("PJX_DEMO_LATENCY", "0")


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
