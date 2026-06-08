from pathlib import Path

from pyjinhx import Registry, Renderer, mutates
from pyjinhx.reactive.cache import clear
from pyjinhx.reactive.mutations import (
    clear_mutations,
    pending_dirtied,
    resolve_effective_dirtied,
)
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton
from tests.ui.reactive.reactive_counter import ReactiveCounter  # noqa: F401
from tests.ui.reactive.store import state

UI_ROOT = Path(__file__).parent / "ui" / "reactive"


@mutates("todos")
def _mutate_todos() -> None:
    state["remaining"] -= 1


def test_mutates_accumulates_pending_dirtied():
    clear_mutations()
    _mutate_todos()
    assert pending_dirtied() == {"todos"}


def test_resolve_effective_dirtied_merges_pending():
    clear_mutations()
    _mutate_todos()
    effective = resolve_effective_dirtied(
        dirtied=None,
        mounted=[],
        own_keys={"todos"},
    )
    assert effective == {"todos"}


def test_render_merges_pending_dirtied_when_omitted():
    clear()
    clear_mutations()
    prev = Renderer.peek_default_environment()
    Renderer.set_default_environment(UI_ROOT)
    try:
        _mutate_todos()
        manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
        with Registry.request_scope():
            out = str(ReactiveClearButton.render(mounted=manifest))
        assert "outerHTML:[data-pjx-id='counter']" in out
        assert pending_dirtied() == set()
    finally:
        Renderer.set_default_environment(prev)


def test_explicit_dirtied_overrides_pending():
    clear()
    clear_mutations()
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
    clear_mutations()
    with Registry.request_scope():
        _mutate_todos()
        assert pending_dirtied() == {"todos"}
    assert pending_dirtied() == set()
