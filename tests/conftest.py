import pytest

from pyjinhx.cache import clear as clear_load_cache


@pytest.fixture(autouse=True)
def _isolate_load_cache():
    """The load() cache is process-global; clear it around every test for isolation."""
    clear_load_cache()
    yield
    clear_load_cache()
