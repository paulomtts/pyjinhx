import os
from unittest.mock import patch

import pytest

from pyjinhx import (
    CacheScope,
    PyJinhxSettings,
    configure_pyjinhx,
    get_load_cache_scope,
    pyjinhx_lifespan,
    shutdown_pyjinhx,
)
from pyjinhx.invalidation import reset_invalidation_state


@pytest.fixture(autouse=True)
def _clean_config_state():
    shutdown_pyjinhx()
    reset_invalidation_state()
    yield
    shutdown_pyjinhx()
    reset_invalidation_state()


def test_pyjinhx_settings_default_is_request():
    assert PyJinhxSettings().cache_scope == CacheScope.REQUEST


def test_configure_pyjinhx_sets_cache_scope():
    configure_pyjinhx(cache_scope=CacheScope.NONE)
    assert get_load_cache_scope() == CacheScope.NONE


def test_configure_pyjinhx_accepts_settings_object():
    settings = PyJinhxSettings(cache_scope=CacheScope.REQUEST)
    configure_pyjinhx(settings)
    assert get_load_cache_scope() == CacheScope.REQUEST


def test_pyjinhx_lifespan_context_manager():
    with pyjinhx_lifespan(cache_scope=CacheScope.REQUEST):
        assert get_load_cache_scope() == CacheScope.REQUEST
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
