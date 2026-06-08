from pathlib import Path

import pytest

from pyjinhx import LoadCache, Registry, Renderer, mutates, mutation_scope
from pyjinhx.reactive.mutations import MutationTracker
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton
from tests.ui.reactive.reactive_counter import ReactiveCounter  # noqa: F401
from tests.ui.reactive.store import state

UI_ROOT = Path(__file__).parent / "ui" / "reactive"


@mutates("todos")
def _mutate_todos() -> None:
    state["remaining"] -= 1


def test_mutates_accumulates_pending_dirtied():
    MutationTracker.clear()
    _mutate_todos()
    assert MutationTracker.pending() == {"todos"}


def test_resolve_effective_dirtied_merges_pending():
    MutationTracker.clear()
    _mutate_todos()
    effective = MutationTracker.resolve_effective_dirtied(
        dirtied=None,
        mounted=[],
        own_keys={"todos"},
    )
    assert effective == {"todos"}


def test_render_merges_pending_dirtied_when_omitted():
    LoadCache.clear()
    MutationTracker.clear()
    prev = Renderer.peek_default_environment()
    Renderer.set_default_environment(UI_ROOT)
    try:
        _mutate_todos()
        manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
        with Registry.request_scope():
            out = str(ReactiveClearButton.render(mounted=manifest))
        assert "outerHTML:[data-pjx-id='counter']" in out
        assert MutationTracker.pending() == set()
    finally:
        Renderer.set_default_environment(prev)


def test_explicit_dirtied_overrides_pending():
    LoadCache.clear()
    MutationTracker.clear()
    prev = Renderer.peek_default_environment()
    Renderer.set_default_environment(UI_ROOT)
    try:
        _mutate_todos()
        manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
        with Registry.request_scope():
            out = str(ReactiveClearButton.render(dirtied=set(), mounted=manifest))
        assert "outerHTML:[data-pjx-id='counter']" not in out
    finally:
        Renderer.set_default_environment(prev)


def test_request_scope_isolates_mutations():
    MutationTracker.clear()
    with Registry.request_scope():
        _mutate_todos()
        assert MutationTracker.pending() == {"todos"}
    assert MutationTracker.pending() == set()


def test_mutation_scope_records_on_success():
    LoadCache.clear()
    MutationTracker.clear()
    with mutation_scope("todos"):
        state["remaining"] -= 1
    assert MutationTracker.pending() == {"todos"}


def test_mutation_scope_does_not_record_on_exception():
    LoadCache.clear()
    MutationTracker.clear()
    with pytest.raises(ValueError):
        with mutation_scope("todos"):
            raise ValueError("mutation failed")
    assert MutationTracker.pending() == set()


def test_mutation_scope_and_mutates_parity_on_success():
    LoadCache.clear()
    MutationTracker.clear()
    with mutation_scope("todos"):
        pass
    scope_pending = MutationTracker.pending()

    LoadCache.clear()
    MutationTracker.clear()
    _mutate_todos()
    mutates_pending = MutationTracker.pending()

    assert scope_pending == mutates_pending == {"todos"}
