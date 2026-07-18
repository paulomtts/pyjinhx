from pathlib import Path

import pytest

from pyjinhx import MutationKey, Registry, Renderer, dirty, mutates
from pyjinhx.cache import LoadCache
from pyjinhx.keys import reactive_key
from pyjinhx.mutations import MutationTracker
from tests.reactive_test_support import Keys, reactive_client
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton
from tests.ui.reactive.reactive_counter import ReactiveCounter  # noqa: F401
from tests.ui.reactive.store import state

UI_ROOT = Path(__file__).parent.parent / "ui" / "reactive"


class _ExtraKeys(MutationKey):
    USERS = "users"


@mutates(Keys.TODOS)
def _mutate_todos() -> None:
    state["remaining"] -= 1


def test_mutates_accumulates_pending_dirtied():
    MutationTracker.clear()
    _mutate_todos()
    assert MutationTracker.pending() == {"todos"}


def test_render_consumes_pending_dirtied():
    LoadCache.clear()
    MutationTracker.clear()
    prev = Renderer.peek_default_environment()
    Renderer.set_default_environment(UI_ROOT)
    try:
        manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
        with Registry.request_scope():
            _mutate_todos()
            with reactive_client(manifest):
                out = str(ReactiveClearButton.render())
        assert "outerHTML:[data-pjx-id='counter']" in out
        assert MutationTracker.pending() == set()
    finally:
        Renderer.set_default_environment(prev)


def test_render_without_pending_skips_oob():
    LoadCache.clear()
    MutationTracker.clear()
    prev = Renderer.peek_default_environment()
    Renderer.set_default_environment(UI_ROOT)
    try:
        manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
        with Registry.request_scope():
            with reactive_client(manifest):
                out = str(ReactiveClearButton.render())
        assert "outerHTML:[data-pjx-id='counter']" not in out
    finally:
        Renderer.set_default_environment(prev)


def test_request_scope_isolates_mutations():
    MutationTracker.clear()
    with Registry.request_scope():
        _mutate_todos()
        assert MutationTracker.pending() == {"todos"}
    assert MutationTracker.pending() == set()


def test_dirty_records_and_invalidates(monkeypatch):
    invalidated: list[set[str]] = []
    monkeypatch.setattr(LoadCache, "invalidate", lambda keys: invalidated.append(set(keys)))
    MutationTracker.clear()
    dirty(Keys.TODOS)
    assert MutationTracker.pending() == {"todos"}
    assert invalidated == [{"todos"}]


def test_dirty_records_multiple_keys():
    MutationTracker.clear()
    dirty(Keys.TODOS, _ExtraKeys.USERS)
    assert MutationTracker.pending() == {"todos", "users"}


def test_dirty_rejects_bare_strings():
    with pytest.raises(TypeError) as excinfo:
        dirty("todos")  # type: ignore[arg-type]  # deliberately passes a bare string
    assert str(excinfo.value).startswith("dirty()")


def test_dirty_accepts_reactive_key():
    MutationTracker.clear()
    dirty(reactive_key(Keys.TODOS, "row-1"))
    assert MutationTracker.pending() == {"todos:row-1"}


def test_mutates_accepts_reactive_key():
    MutationTracker.clear()

    @mutates(reactive_key(Keys.TODOS, "row-2"))
    def _mutate_one_row() -> None:
        pass

    _mutate_one_row()
    assert MutationTracker.pending() == {"todos:row-2"}


def test_mutates_key_kwarg_derives_from_call_args():
    MutationTracker.clear()

    @mutates(Keys.TODOS, key=lambda todo_id: todo_id)
    def toggle(todo_id: str) -> None:
        pass

    toggle("row-3")
    assert MutationTracker.pending() == {"todos:row-3"}


def test_mutates_key_kwarg_reflects_each_call():
    MutationTracker.clear()

    @mutates(Keys.TODOS, key=lambda todo_id: todo_id)
    def toggle(todo_id: str) -> None:
        pass

    toggle("row-1")
    assert MutationTracker.pending() == {"todos:row-1"}
    MutationTracker.clear()
    toggle("row-2")
    assert MutationTracker.pending() == {"todos:row-2"}


def test_mutates_key_kwarg_applies_to_every_key():
    MutationTracker.clear()

    @mutates(Keys.TODOS, _ExtraKeys.USERS, key=lambda user_id: user_id)
    def touch(user_id: str) -> None:
        pass

    touch("7")
    assert MutationTracker.pending() == {"todos:7", "users:7"}


def test_mutates_key_kwarg_reloads_only_the_matching_instance():
    from pyjinhx.reactive import oob_swaps
    from tests.ui.reactive.counted_row import CountedRow, Keys as RowKeys  # noqa: F401

    LoadCache.clear()
    CountedRow.load_calls.clear()
    MutationTracker.clear()

    @mutates(RowKeys.ROW, key=lambda row_id: row_id)
    def toggle_row(row_id: str) -> None:
        pass

    manifest = [
        {"id": "row-1", "type": "CountedRow", "load": "1", "hash": "stale"},
        {"id": "row-2", "type": "CountedRow", "load": "2", "hash": "stale"},
    ]
    toggle_row("2")
    out = str(oob_swaps(MutationTracker.pending(), manifest))
    assert CountedRow.load_calls == ["2"]
    assert "outerHTML:[data-pjx-id='row-2']" in out
    assert "outerHTML:[data-pjx-id='row-1']" not in out


def test_dirty_without_args_is_noop():
    MutationTracker.clear()
    dirty()
    assert MutationTracker.pending() == set()


def test_dirty_consumed_by_reactive_render():
    LoadCache.clear()
    MutationTracker.clear()
    prev = Renderer.peek_default_environment()
    Renderer.set_default_environment(UI_ROOT)
    try:
        manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
        with Registry.request_scope():
            dirty(Keys.TODOS)
            with reactive_client(manifest):
                out = str(ReactiveClearButton.render())
        assert "outerHTML:[data-pjx-id='counter']" in out
        assert MutationTracker.pending() == set()
    finally:
        Renderer.set_default_environment(prev)
