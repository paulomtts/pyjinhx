"""
SQLite invalidation backend for single-host multi-worker CacheScope.PROCESS setups.

Uses a shared SQLite file as a durable event log for cross-process load-cache
invalidation fan-out. Zero external infrastructure (``sqlite3`` is stdlib). The
trade-offs vs Redis: single-host only (SQLite locking is unreliable over network
filesystems) and polling-based delivery.

``:memory:`` is unsupported here — each process gets a private in-memory database,
so there is no cross-process fan-out. Use a real file path. WAL mode leaves
``-wal``/``-shm`` sidecar files next to the database; this is expected.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import closing

from pyjinhx.cache import InvalidationBackend

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL = "pyjinhx:invalidate"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pjx_invalidation (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id TEXT    NOT NULL,
    channel     TEXT    NOT NULL,
    keys_json   TEXT    NOT NULL,
    created_at  REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pjx_invalidation_created_at
    ON pjx_invalidation (created_at);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with WAL + busy_timeout and ensure the schema exists."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(_SCHEMA)
    return conn


class SqliteInvalidationBackend(InvalidationBackend):
    """SQLite event-log fan-out for ``invalidate()`` across single-host workers."""

    def __init__(
        self,
        db_path: str,
        *,
        channel: str = DEFAULT_CHANNEL,
        poll_interval: float = 0.5,
        retention: float = 5.0,
    ) -> None:
        self._db_path = db_path
        self._channel = channel
        self._poll_interval = poll_interval
        self._retention = retention
        self._instance_id = uuid.uuid4().hex
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._handler: Callable[[frozenset[str]], None] | None = None

    def publish(self, keys: frozenset[str]) -> None:
        if not keys:
            return
        now = time.time()
        payload = json.dumps(sorted(keys))
        with closing(_connect(self._db_path)) as conn, conn:
            conn.execute(
                "INSERT INTO pjx_invalidation "
                "(instance_id, channel, keys_json, created_at) VALUES (?, ?, ?, ?)",
                (self._instance_id, self._channel, payload, now),
            )
            conn.execute(
                "DELETE FROM pjx_invalidation WHERE created_at < ?",
                (now - self._retention,),
            )

    def start(self, handler: Callable[[frozenset[str]], None]) -> None:
        if self._thread is not None:
            return
        # Pre-initialise the schema from the calling thread so the poll
        # thread's _connect() doesn't race with publish() on a brand-new file.
        with closing(_connect(self._db_path)):
            pass
        self._handler = handler
        self._stop_event.clear()
        self._ready_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="pyjinhx-sqlite-invalidation",
            daemon=True,
        )
        self._thread.start()
        # Wait for the poll thread to seed its cursor before returning, so
        # callers can safely call publish() immediately after start().
        if not self._ready_event.wait(timeout=5.0):
            logger.warning(
                "SQLite invalidation poll thread did not become ready within 5 s; "
                "the listener may be silently dead."
            )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._handler = None

    def _poll_loop(self) -> None:
        # Retry transient lock errors (e.g. WAL setup races) until we get a
        # clean connection or stop is requested.  Note: start() and publish()
        # both call _connect() synchronously in the caller's thread, so a
        # genuinely bad db_path (e.g. missing directory) is already surfaced
        # loudly before the poll thread ever runs.  A persistent failure here
        # (e.g. concurrent exclusive lock that never releases) will keep
        # retrying until stop() is called, then log an error (see below).
        conn: sqlite3.Connection | None = None
        _any_connect_failure = False
        while conn is None and not self._stop_event.is_set():
            try:
                conn = _connect(self._db_path)
            except sqlite3.OperationalError:
                _any_connect_failure = True
                logger.debug("SQLite connect retry (database locked)", exc_info=True)
                self._stop_event.wait(0.05)
        if conn is None:
            if _any_connect_failure:
                logger.error(
                    "SQLite invalidation listener could not establish a connection "
                    "to %r and will not receive any invalidations.",
                    self._db_path,
                )
            self._ready_event.set()
            return
        with closing(conn):
            # seed cursor to the current tail so history is not replayed
            cursor = conn.execute(
                "SELECT COALESCE(MAX(id), 0) FROM pjx_invalidation"
            ).fetchone()[0]
            self._ready_event.set()
            while not self._stop_event.wait(self._poll_interval):
                try:
                    rows = conn.execute(
                        "SELECT id, keys_json FROM pjx_invalidation "
                        "WHERE id > ? AND channel = ? AND instance_id != ? "
                        "ORDER BY id",
                        (cursor, self._channel, self._instance_id),
                    ).fetchall()
                    for row_id, keys_json in rows:
                        cursor = row_id
                        if self._handler is None:
                            continue
                        try:
                            parsed = json.loads(keys_json)
                        except json.JSONDecodeError:
                            logger.warning(
                                "Ignoring invalid invalidation payload: %r", keys_json
                            )
                            continue
                        if not isinstance(parsed, list):
                            continue
                        self._handler(frozenset(str(key) for key in parsed))
                except Exception:
                    logger.exception("Error in SQLite invalidation poll loop")
