import os
from unittest.mock import patch

from pyjinhx import PjxSettings
from pyjinhx.cache import CacheScope, InvalidationBackend, LoadCache
from pyjinhx.config import configure_pyjinhx, shutdown_pyjinhx


class _StubBackend(InvalidationBackend):
    def publish(self, keys: frozenset[str]) -> None:
        pass

    def start(self, handler) -> None:
        pass

    def stop(self) -> None:
        pass


def test_pyjinhx_settings_default_has_no_backend():
    assert PjxSettings().invalidation_backend is None


def test_configure_pyjinhx_no_backend_is_request():
    configure_pyjinhx()
    assert LoadCache.scope() == CacheScope.REQUEST


def test_configure_pyjinhx_with_backend_is_process():
    configure_pyjinhx(invalidation_backend=_StubBackend())
    assert LoadCache.scope() == CacheScope.PROCESS


def test_configure_pyjinhx_accepts_settings_object():
    settings = PjxSettings()
    configure_pyjinhx(settings)
    assert LoadCache.scope() == CacheScope.REQUEST


def test_from_env_defaults_to_request():
    with patch.dict(os.environ, {}, clear=True):
        settings = PjxSettings.from_env()
    assert settings.invalidation_backend is None
    configure_pyjinhx(settings)
    assert LoadCache.scope() == CacheScope.REQUEST


def test_from_env_process_with_redis_url():
    with patch.dict(os.environ, {"REDIS_URL": "memory://"}, clear=True):
        settings = PjxSettings.from_env()
    assert settings.invalidation_backend is not None
    configure_pyjinhx(settings)
    assert LoadCache.scope() == CacheScope.PROCESS


def test_configure_with_backend_is_process_and_keeps_backend():
    backend = _StubBackend()
    resolved = configure_pyjinhx(invalidation_backend=backend)
    assert resolved.invalidation_backend is backend
    assert LoadCache.scope() == CacheScope.PROCESS


def test_settings_object_not_clobbered_by_default_kwargs():
    # regression: default kwargs must not overwrite an explicit settings=
    # (an explicit backend previously reverted to None, nulling PROCESS config).
    backend = _StubBackend()
    resolved = configure_pyjinhx(PjxSettings(invalidation_backend=backend))
    assert resolved.invalidation_backend is backend
    assert LoadCache.scope() == CacheScope.PROCESS


def test_settings_process_keeps_invalidation_backend():
    backend = _StubBackend()
    resolved = configure_pyjinhx(PjxSettings(invalidation_backend=backend))
    assert resolved.invalidation_backend is backend
    assert LoadCache.scope() == CacheScope.PROCESS


def test_explicit_kwarg_still_overrides_settings():
    # explicit invalidation_backend=None overrides a backend on the settings object,
    # which derives REQUEST instead of PROCESS.
    resolved = configure_pyjinhx(
        PjxSettings(invalidation_backend=_StubBackend()), invalidation_backend=None
    )
    assert resolved.invalidation_backend is None
    assert LoadCache.scope() == CacheScope.REQUEST


def test_from_env_with_sqlite_db(tmp_path):
    from pyjinhx.integrations.sqlite import SqliteInvalidationBackend

    db = str(tmp_path / "inval.db")
    with patch.dict(os.environ, {"PJX_INVALIDATION_DB": db}, clear=True):
        settings = PjxSettings.from_env()
    assert isinstance(settings.invalidation_backend, SqliteInvalidationBackend)
    configure_pyjinhx(settings)
    assert LoadCache.scope() == CacheScope.PROCESS
    shutdown_pyjinhx()


def test_from_env_redis_wins_over_sqlite(tmp_path):
    from pyjinhx.integrations.redis import RedisInvalidationBackend

    db = str(tmp_path / "inval.db")
    with patch.dict(
        os.environ, {"REDIS_URL": "memory://", "PJX_INVALIDATION_DB": db}, clear=True
    ):
        settings = PjxSettings.from_env()
    assert isinstance(settings.invalidation_backend, RedisInvalidationBackend)


def test_inject_htmx_defaults_true():
    assert PjxSettings().inject_htmx is True


def test_configure_pyjinhx_toggles_inject_htmx():
    import pyjinhx.assets as assets

    configure_pyjinhx(inject_htmx=False)
    assert assets._inject_htmx is False
    configure_pyjinhx(inject_htmx=True)
    assert assets._inject_htmx is True


def test_from_env_reads_inject_htmx():
    with patch.dict(os.environ, {"PJX_INJECT_HTMX": "false"}, clear=True):
        settings = PjxSettings.from_env()
    assert settings.inject_htmx is False
    with patch.dict(os.environ, {}, clear=True):
        assert PjxSettings.from_env().inject_htmx is True


def test_htmx_redirects_defaults_false():
    assert PjxSettings().htmx_redirects is False


def test_configure_pyjinhx_resolves_htmx_redirects():
    resolved = configure_pyjinhx(htmx_redirects=True)
    assert resolved.htmx_redirects is True


def test_from_env_reads_htmx_redirects():
    with patch.dict(os.environ, {"PJX_HTMX_REDIRECTS": "true"}, clear=True):
        assert PjxSettings.from_env().htmx_redirects is True
    with patch.dict(os.environ, {}, clear=True):
        assert PjxSettings.from_env().htmx_redirects is False
