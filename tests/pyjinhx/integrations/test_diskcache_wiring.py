"""The diskcache-backed tier-2 cache: extra wiring and CacheBackend conformance."""

import subprocess
import sys
import textwrap
import time

import pytest

from pyjinhx.reactive.backend import MISS, CacheBackend

diskcache = pytest.importorskip("diskcache")

from pyjinhx.integrations.diskcache import DiskCacheBackend  # noqa: E402


def test_importing_bare_pyjinhx_does_not_need_the_extra():
    # A subprocess with diskcache blocked at the import hook is the only honest
    # check here: the dev environment installs the extra, so an in-process
    # import would pass whether or not the eager-import rule is respected.
    script = textwrap.dedent("""
        import sys

        class Blocker:
            # find_spec(), not the deprecated find_module(): CPython's import
            # machinery (3.12+) never calls find_module() on a meta_path entry
            # that only defines it, so a Blocker built on find_module() is
            # inert - the import succeeds either way and the test is honest
            # only by accident. find_spec() is the hook actually consulted.
            def find_spec(self, name, path=None, target=None):
                if name == "diskcache" or name.startswith("diskcache."):
                    raise ImportError("diskcache is not installed")
                return None

        sys.meta_path.insert(0, Blocker())
        import pyjinhx
        import pyjinhx.config
        assert "diskcache" not in sys.modules
        print("ok")
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_the_backend_satisfies_the_protocol(tmp_path):
    assert isinstance(DiskCacheBackend(tmp_path), CacheBackend)


def test_the_backend_wraps_a_fanout_cache_not_a_plain_cache(tmp_path):
    # A single Cache means one SQLite write lock every worker queues behind,
    # which is the thing the sharded FanoutCache exists to avoid.
    backend = DiskCacheBackend(tmp_path)
    assert isinstance(backend._cache, diskcache.FanoutCache)


def test_get_on_an_empty_cache_returns_miss(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    result = backend.get("pjx:1:app.Widget:todos")
    assert result is MISS
    assert result is not None


def test_put_then_get_round_trips_the_value(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("todos", [1, 2, 3], tags=(), ttl=None)
    assert backend.get("todos") == [1, 2, 3]


def test_a_cached_none_round_trips_as_none_not_miss(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("todos", None, tags=(), ttl=None)
    assert backend.get("todos") is None


def test_a_re_put_replaces_the_entry(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("todos", [1], tags=(), ttl=None)
    backend.put("todos", [2], tags=(), ttl=None)
    assert backend.get("todos") == [2]


def test_an_entry_past_its_ttl_reads_as_a_miss(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("todos", [1, 2, 3], tags=(), ttl=0.05)
    assert backend.get("todos") == [1, 2, 3]
    time.sleep(0.1)
    assert backend.get("todos") is MISS


def test_a_none_ttl_never_expires_on_its_own(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("todos", [1, 2, 3], tags=(), ttl=None)
    time.sleep(0.1)
    assert backend.get("todos") == [1, 2, 3]


def test_evicting_a_tag_drops_the_entries_carrying_it(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("todos", [1], tags=("todos",), ttl=None)
    backend.put("users", [2], tags=("users",), ttl=None)
    backend.evict(("todos",))
    assert backend.get("todos") is MISS
    assert backend.get("users") == [2]


def test_evicting_a_tag_that_matches_nothing_is_a_no_op(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("todos", [1], tags=("todos",), ttl=None)
    backend.evict(("nothing-has-this-tag",))
    backend.evict(())
    assert backend.get("todos") == [1]


def test_clear_empties_the_cache(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("todos", [1], tags=("todos",), ttl=None)
    backend.put("users", [2], tags=("users",), ttl=None)
    backend.clear()
    assert backend.get("todos") is MISS
    assert backend.get("users") is MISS


def test_close_is_callable_the_way_shutdown_calls_it(tmp_path):
    # shutdown_pyjinhx() reaches for close() by name on whatever backend is
    # configured, so the attribute has to be there on the instance.
    backend = DiskCacheBackend(tmp_path)
    close = getattr(backend, "close", None)
    assert close is not None
    close()
