import pytest

from pyjinhx.cache import CacheScope, InvalidationHub, LoadCache
from pyjinhx.client import ClientBackend
from pyjinhx.mutations import MutationTracker
from pyjinhx import Registry


@pytest.fixture(autouse=True)
def _isolate_reactive_state(request: pytest.FixtureRequest):
    """
    Override the global _isolate_reactive_state fixture for tests that need to run
    outside a request scope (like response directives tests).

    For test_response_directives, just do the basic cleanup without wrapping in a scope.
    """
    if "test_response_directives" in request.node.nodeid:
        # For response directives tests, just do cleanup without request scope wrapper
        original_scope = LoadCache.scope()
        LoadCache.clear()
        MutationTracker.clear()
        InvalidationHub.reset()
        ClientBackend.reset()
        Registry.clear_instances()
        LoadCache.set_scope(CacheScope.REQUEST)
        yield
        LoadCache.clear()
        MutationTracker.clear()
        InvalidationHub.reset()
        ClientBackend.reset()
        Registry.clear_instances()
        LoadCache.set_scope(original_scope)
    else:
        # For all other tests, use the original behavior (wrap in request scope)
        original_scope = LoadCache.scope()
        LoadCache.clear()
        MutationTracker.clear()
        InvalidationHub.reset()
        ClientBackend.reset()
        Registry.clear_instances()
        LoadCache.set_scope(CacheScope.REQUEST)
        with Registry.request_scope():
            yield
        LoadCache.clear()
        MutationTracker.clear()
        InvalidationHub.reset()
        ClientBackend.reset()
        Registry.clear_instances()
        LoadCache.set_scope(original_scope)
