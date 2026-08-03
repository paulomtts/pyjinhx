from pyjinhx_v0.cache import CacheScope, InvalidationHub, LoadCache
from pyjinhx_v0.config import configure_pyjinhx, shutdown_pyjinhx


def test_configure_pyjinhx_defaults_to_request_scope():
    shutdown_pyjinhx()
    InvalidationHub.reset()
    configure_pyjinhx()
    assert LoadCache.scope() == CacheScope.REQUEST
