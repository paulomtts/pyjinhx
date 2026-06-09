from pyjinhx import CacheScope, LoadCache, configure_pyjinhx, shutdown_pyjinhx
from pyjinhx.reactive.cache import InvalidationHub


def test_configure_pyjinhx_defaults_to_request_scope():
    shutdown_pyjinhx()
    InvalidationHub.reset()
    configure_pyjinhx()
    assert LoadCache.scope() == CacheScope.REQUEST
