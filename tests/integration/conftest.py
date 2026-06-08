import pytest
from fastapi.testclient import TestClient

from examples.reactive_todo.app import app
from examples.reactive_todo.invalidation import configure_load_cache, shutdown_load_cache


@pytest.fixture
def client():
    configure_load_cache()
    with TestClient(app) as test_client:
        yield test_client
    shutdown_load_cache()
