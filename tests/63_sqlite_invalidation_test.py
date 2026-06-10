import json
import sqlite3
import threading
import time

from pyjinhx.cache import CacheScope, InvalidationHub, LoadCache
from pyjinhx.integrations.sqlite import DEFAULT_CHANNEL, SqliteInvalidationBackend
from tests.ui.reactive.cached_widget import CachedWidget, load_calls


def test_publish_inserts_one_row(tmp_path):
    db = str(tmp_path / "inval.db")
    backend = SqliteInvalidationBackend(db)
    backend.publish(frozenset({"widgets", "gadgets"}))
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT channel, keys_json FROM pjx_invalidation").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][0] == DEFAULT_CHANNEL
    assert json.loads(rows[0][1]) == ["gadgets", "widgets"]


def test_publish_empty_keys_is_noop(tmp_path):
    db = tmp_path / "inval.db"
    SqliteInvalidationBackend(str(db)).publish(frozenset())
    assert not db.exists()


def test_fanout_delivers_keys_to_other_instance(tmp_path):
    db = str(tmp_path / "inval.db")
    got: list[frozenset[str]] = []
    received = threading.Event()

    def handler(keys):
        got.append(keys)
        received.set()

    publisher = SqliteInvalidationBackend(db, poll_interval=0.05)
    listener = SqliteInvalidationBackend(db, poll_interval=0.05)
    listener.start(handler)
    try:
        publisher.publish(frozenset({"widgets"}))
        assert received.wait(timeout=3.0)
        assert got == [frozenset({"widgets"})]
    finally:
        listener.stop()


def test_publisher_does_not_receive_its_own_events(tmp_path):
    db = str(tmp_path / "inval.db")
    got: list[frozenset[str]] = []
    backend = SqliteInvalidationBackend(db, poll_interval=0.05)
    backend.start(got.append)
    try:
        backend.publish(frozenset({"widgets"}))
        time.sleep(0.3)
        assert got == []
    finally:
        backend.stop()


def test_different_channels_are_isolated(tmp_path):
    db = str(tmp_path / "inval.db")
    got: list[frozenset[str]] = []
    listener = SqliteInvalidationBackend(db, channel="app-a", poll_interval=0.05)
    publisher = SqliteInvalidationBackend(db, channel="app-b", poll_interval=0.05)
    listener.start(got.append)
    try:
        publisher.publish(frozenset({"widgets"}))
        time.sleep(0.3)
        assert got == []
    finally:
        listener.stop()


def test_history_before_start_is_not_replayed(tmp_path):
    db = str(tmp_path / "inval.db")
    publisher = SqliteInvalidationBackend(db, poll_interval=0.05)
    publisher.publish(frozenset({"old"}))
    got: list[frozenset[str]] = []
    received = threading.Event()

    def handler(keys):
        got.append(keys)
        received.set()

    listener = SqliteInvalidationBackend(db, poll_interval=0.05)
    listener.start(handler)
    try:
        publisher.publish(frozenset({"new"}))
        assert received.wait(timeout=3.0)
        assert got == [frozenset({"new"})]
    finally:
        listener.stop()


def test_publish_prunes_rows_older_than_retention(tmp_path):
    db = str(tmp_path / "inval.db")
    backend = SqliteInvalidationBackend(db, retention=60.0)
    backend.publish(frozenset({"fresh"}))
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(
            "INSERT INTO pjx_invalidation "
            "(instance_id, channel, keys_json, created_at) VALUES (?, ?, ?, ?)",
            ("other", DEFAULT_CHANNEL, '["stale"]', 0.0),
        )
    conn.close()
    backend.publish(frozenset({"trigger"}))
    conn = sqlite3.connect(db)
    payloads = [r[0] for r in conn.execute(
        "SELECT keys_json FROM pjx_invalidation ORDER BY id"
    ).fetchall()]
    conn.close()
    assert '["stale"]' not in payloads
    assert '["fresh"]' in payloads
    assert '["trigger"]' in payloads


def test_start_twice_is_a_noop(tmp_path):
    db = str(tmp_path / "inval.db")
    backend = SqliteInvalidationBackend(db, poll_interval=0.05)
    backend.start(lambda keys: None)
    first_thread = backend._thread
    backend.start(lambda keys: None)
    try:
        assert backend._thread is first_thread
    finally:
        backend.stop()


def test_stop_is_idempotent(tmp_path):
    db = str(tmp_path / "inval.db")
    backend = SqliteInvalidationBackend(db, poll_interval=0.05)
    backend.start(lambda keys: None)
    backend.stop()
    backend.stop()
    assert backend._thread is None


def test_sqlite_invalidate_evicts_process_cache(tmp_path):
    db = str(tmp_path / "inval.db")
    LoadCache.clear()
    load_calls["count"] = 0
    original_scope = LoadCache.scope()
    try:
        LoadCache.set_scope(CacheScope.PROCESS)
        backend = SqliteInvalidationBackend(db, poll_interval=0.05)
        InvalidationHub.set_backend(backend)
        InvalidationHub.start_listener()
        CachedWidget.load()
        assert load_calls["count"] == 1
        LoadCache.invalidate({"widgets"})
        load_calls["count"] = 0
        CachedWidget.load()
        assert load_calls["count"] == 1
    finally:
        InvalidationHub.stop_listener()
        InvalidationHub.reset()
        LoadCache.set_scope(original_scope)
