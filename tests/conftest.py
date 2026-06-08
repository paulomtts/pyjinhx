from collections.abc import Generator

import pytest

from pyjinhx import CacheScope, Registry, get_load_cache_scope, set_load_cache_scope
from pyjinhx.cache import clear as clear_load_cache
from pyjinhx.invalidation import reset_invalidation_state
from pyjinhx.mutations import clear_mutations


@pytest.fixture(autouse=True)
def _isolate_reactive_state() -> Generator[None, None, None]:
    """
    Reset pyjinhx reactive state around every test inside a request scope.

    Mirrors production: load() cache (REQUEST scope), instance registry, and
    mutation tracking are all request-scoped.
    """
    original_scope = get_load_cache_scope()
    clear_load_cache()
    clear_mutations()
    reset_invalidation_state()
    Registry.clear_instances()
    set_load_cache_scope(CacheScope.PROCESS)
    with Registry.request_scope():
        yield
    clear_load_cache()
    clear_mutations()
    reset_invalidation_state()
    Registry.clear_instances()
    set_load_cache_scope(original_scope)
