import pytest
from fastapi.testclient import TestClient

from examples.reactive_todo.app import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
