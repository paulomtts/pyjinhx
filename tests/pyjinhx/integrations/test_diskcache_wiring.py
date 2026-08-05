"""The diskcache-backed tier-2 cache: extra wiring and CacheBackend conformance."""

import logging
import subprocess
import sys
import textwrap
import time

import pytest

from pyjinhx.reactive.backend import MISS, CacheBackend
from pyjinhx.reactive.backend_health import is_degraded

diskcache = pytest.importorskip("diskcache")

from pyjinhx.integrations.diskcache import DiskCacheBackend


class Unpicklable:
    """A value whose instances refuse to pickle, the way a live handle would."""

    def __reduce__(self):
        raise TypeError("Unpicklable does not pickle")


class AlsoUnpicklable:
    """A second such class, so log-once-per-class is distinguishable from once-ever."""

    def __reduce__(self):
        raise TypeError("AlsoUnpicklable does not pickle")


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
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
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


def test_an_entry_with_several_tags_is_evicted_by_any_one_of_them(tmp_path):
    # A fresh directory per case: an entry evicted by its first tag proves
    # nothing about the second unless the second is tried on a live entry.
    for tag in ("todos", "users"):
        backend = DiskCacheBackend(tmp_path / tag)
        backend.put("summary", [1], tags=("todos", "users"), ttl=None)
        backend.evict((tag,))
        assert backend.get("summary") is MISS


def test_evict_drops_every_entry_matching_any_given_tag(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("todos", [1], tags=("todos",), ttl=None)
    backend.put("users", [2], tags=("users",), ttl=None)
    backend.put("orders", [3], tags=("orders",), ttl=None)
    backend.evict(("todos", "users"))
    assert backend.get("todos") is MISS
    assert backend.get("users") is MISS
    assert backend.get("orders") == [3]


def test_an_entry_reachable_from_two_evicted_tags_is_dropped_once(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("summary", [1], tags=("todos", "users"), ttl=None)
    backend.evict(("todos", "users"))
    assert backend.get("summary") is MISS
    # Whatever bookkeeping the double match left behind must not resurrect the
    # key or poison the tags for the next entry stored under them.
    backend.put("summary", [2], tags=("todos", "users"), ttl=None)
    assert backend.get("summary") == [2]


def test_re_putting_a_key_drops_its_old_tags(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("summary", [1], tags=("todos",), ttl=None)
    backend.put("summary", [2], tags=("users",), ttl=None)
    backend.evict(("todos",))
    assert backend.get("summary") == [2]
    backend.evict(("users",))
    assert backend.get("summary") is MISS


def test_evict_with_no_tags_is_a_no_op(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("summary", [1], tags=("todos", "users"), ttl=None)
    backend.evict(())
    assert backend.get("summary") == [1]


def test_put_with_no_tags_is_never_evicted_by_a_later_evict_call(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("summary", [1], tags=(), ttl=None)
    backend.evict(("todos", "users", ""))
    assert backend.get("summary") == [1]


def test_a_multi_tag_entry_still_expires_on_its_ttl(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("summary", [1], tags=("todos", "users"), ttl=0.05)
    assert backend.get("summary") == [1]
    time.sleep(0.1)
    assert backend.get("summary") is MISS


def test_multi_tag_semantics_hold_across_two_backend_instances_sharing_a_directory(
    tmp_path,
):
    # The tag index has to live in the cache directory, not in either instance's
    # memory: that is what makes an eviction in one worker visible in the next.
    writer = DiskCacheBackend(tmp_path)
    evictor = DiskCacheBackend(tmp_path)
    writer.put("summary", [1], tags=("todos", "users"), ttl=None)
    evictor.evict(("users",))
    assert writer.get("summary") is MISS


def test_an_eviction_in_one_process_is_visible_to_another_process_on_its_next_read(
    tmp_path,
):
    # Two backend instances in one interpreter share a directory but also share
    # a process; real workers do not. Only separate OS processes exercise the
    # SQLite connections the directory-resident tag index has to reach across.
    writer_script = textwrap.dedent("""
        import sys

        from pyjinhx.integrations.diskcache import DiskCacheBackend

        backend = DiskCacheBackend(sys.argv[1])
        backend.put("summary", [1], tags=("todos",), ttl=None)
        assert backend.get("summary") == [1]
        backend.close()
        print("ok")
    """)
    reader_script = textwrap.dedent("""
        import sys

        from pyjinhx.reactive.backend import MISS
        from pyjinhx.integrations.diskcache import DiskCacheBackend

        backend = DiskCacheBackend(sys.argv[1])
        result = backend.get("summary")
        backend.close()
        assert result is MISS, result
        print("ok")
    """)

    # Opened before the writer runs, so the read below goes through connections
    # that predate the entry rather than ones opened after it landed.
    evictor = DiskCacheBackend(tmp_path)

    written = subprocess.run(
        [sys.executable, "-c", writer_script, str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert written.returncode == 0, written.stderr
    assert "ok" in written.stdout

    assert evictor.get("summary") == [1]

    evictor.evict(("todos",))

    read = subprocess.run(
        [sys.executable, "-c", reader_script, str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert read.returncode == 0, read.stderr
    assert "ok" in read.stdout


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


def test_putting_an_unpicklable_value_does_not_raise(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("summary", Unpicklable(), tags=("todos",), ttl=None)


def test_putting_an_unpicklable_value_leaves_the_key_unset(tmp_path):
    backend = DiskCacheBackend(tmp_path)
    backend.put("summary", Unpicklable(), tags=("todos",), ttl=None)
    assert backend.get("summary") is MISS


def test_putting_an_unpicklable_value_logs_once_per_class(tmp_path, caplog):
    backend = DiskCacheBackend(tmp_path)
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        backend.put("first", Unpicklable(), tags=("todos",), ttl=None)
        backend.put("second", Unpicklable(), tags=("todos",), ttl=None)
    assert len(caplog.records) == 1
    assert "Unpicklable" in caplog.records[0].getMessage()


def test_putting_two_different_unpicklable_classes_each_logs_once(tmp_path, caplog):
    backend = DiskCacheBackend(tmp_path)
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        backend.put("first", Unpicklable(), tags=("todos",), ttl=None)
        backend.put("second", AlsoUnpicklable(), tags=("todos",), ttl=None)
        backend.put("third", AlsoUnpicklable(), tags=("todos",), ttl=None)
    assert len(caplog.records) == 2
    logged = [record.getMessage() for record in caplog.records]
    # Module-qualified, and with the trailing space: "AlsoUnpicklable" contains
    # "Unpicklable", so a bare substring check would pass on the wrong record.
    for cls in (Unpicklable, AlsoUnpicklable):
        name = f"{cls.__module__}.{cls.__qualname__} "
        assert any(name in message for message in logged), name


def test_an_unpicklable_value_does_not_mark_the_backend_degraded(tmp_path):
    # A value that will not pickle is a fact about that value, not a backend
    # that is down - degradation is backend_health.py's separate mechanism.
    backend = DiskCacheBackend(tmp_path)
    backend.put("summary", Unpicklable(), tags=("todos",), ttl=None)
    assert is_degraded(backend) is False
    backend.put("todos", [1], tags=("todos",), ttl=None)
    assert backend.get("todos") == [1]
    backend.evict(("todos",))
    assert backend.get("todos") is MISS
