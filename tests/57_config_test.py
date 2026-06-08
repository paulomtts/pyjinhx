import os
from unittest.mock import patch

from pyjinhx import (
    CacheScope,
    InvalidationBackend,
    LoadCache,
    PyJinhxSettings,
    configure_pyjinhx,
    pyjinhx_lifespan,
    shutdown_pyjinhx,
)


def test_pyjinhx_settings_default_is_request():
    assert PyJinhxSettings().cache_scope == CacheScope.REQUEST


def test_configure_pyjinhx_sets_cache_scope():
    configure_pyjinhx(cache_scope=CacheScope.NONE)
    assert LoadCache.scope() == CacheScope.NONE


def test_configure_pyjinhx_accepts_settings_object():
    settings = PyJinhxSettings(cache_scope=CacheScope.REQUEST)
    configure_pyjinhx(settings)
    assert LoadCache.scope() == CacheScope.REQUEST


def test_pyjinhx_lifespan_context_manager():
    with pyjinhx_lifespan(cache_scope=CacheScope.REQUEST):
        assert LoadCache.scope() == CacheScope.REQUEST
    shutdown_pyjinhx()


def test_from_env_defaults_to_request():
    with patch.dict(os.environ, {}, clear=True):
        settings = PyJinhxSettings.from_env()
    assert settings.cache_scope == CacheScope.REQUEST
    assert settings.invalidation_backend is None


def test_from_env_process_with_redis_url():
    with patch.dict(
        os.environ,
        {"PJX_LOAD_CACHE_SCOPE": "process", "REDIS_URL": "memory://"},
        clear=True,
    ):
        settings = PyJinhxSettings.from_env()
    assert settings.cache_scope == CacheScope.PROCESS
    assert settings.invalidation_backend is not None


class _StubBackend(InvalidationBackend):
    def publish(self, keys: frozenset[str]) -> None:
        pass

    def start(self, handler) -> None:
        pass

    def stop(self) -> None:
        pass


def test_configure_warns_when_backend_set_with_request_scope(caplog):
    import logging

    caplog.set_level(logging.WARNING, logger="pyjinhx")
    configure_pyjinhx(
        cache_scope=CacheScope.REQUEST,
        invalidation_backend=_StubBackend(),
    )
    assert LoadCache.scope() == CacheScope.REQUEST
    assert any("invalidation_backend" in record.message for record in caplog.records)
