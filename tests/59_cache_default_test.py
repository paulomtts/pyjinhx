from pyjinhx import CacheScope, configure_pyjinhx, get_load_cache_scope, shutdown_pyjinhx
from pyjinhx.reactive.invalidation import reset_invalidation_state


def test_configure_pyjinhx_defaults_to_request_scope():
    shutdown_pyjinhx()
    reset_invalidation_state()
    configure_pyjinhx()
    assert get_load_cache_scope() == CacheScope.REQUEST
