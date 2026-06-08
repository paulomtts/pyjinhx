from collections.abc import Generator

import pytest

from pyjinhx import Registry
from pyjinhx.cache import clear as clear_load_cache
from pyjinhx.mutations import clear_mutations


@pytest.fixture(autouse=True)
def _isolate_reactive_state() -> Generator[None, None, None]:
    """
    Reset pyjinhx's process-global state around every test.

    - The load() cache is process-global.
    - The instance registry persists across tests (it is a ContextVar), and the
      renderer injects every registered instance into the template context by id,
      so a leftover instance whose id collides with another test's component field
      or template variable would shadow it. Clear both for isolation.
    """
    clear_load_cache()
    clear_mutations()
    Registry.clear_instances()
    yield
    clear_load_cache()
    clear_mutations()
    Registry.clear_instances()
