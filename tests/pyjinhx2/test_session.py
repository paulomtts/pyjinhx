"""request_scope's four ContextVars: fresh in, prior state out.

The four pieces of per-request mutable state (RenderSession asset slot, instance
registry, dirtied keys, cache store) are the entire ContextVar half of the
mutable-state census. These tests pin the container lifecycle - creation,
nesting, exception cleanup, thread isolation - not any read/write semantics,
which land with the modules that consume them.
"""

import threading
from typing import Any, cast

import pytest

from pyjinhx2 import session as session_module


def test_getters_return_empty_defaults_outside_any_scope():
    """An unset ContextVar must read as an empty container, never raise. Callers
    outside a request (tests, scripts, module import time) are legitimate."""
    assert session_module.current_session() is None
    assert session_module.get_instances() == {}
    assert session_module.get_dirtied() == set()
    assert session_module.get_cache_store() == {}


def test_request_scope_binds_fresh_empty_state_for_all_four_pieces():
    with session_module.request_scope() as session:
        assert isinstance(session, session_module.RenderSession)
        assert session_module.current_session() is session
        assert session.asset_paths == set()
        assert session_module.get_instances() == {}
        assert session_module.get_dirtied() == set()
        assert session_module.get_cache_store() == {}


def test_containers_bound_by_the_scope_are_the_live_ones():
    """Writes through the getters must land in the scope's containers, not copies."""
    with session_module.request_scope():
        session_module.get_instances()["Card_a"] = "instance"
        session_module.get_dirtied().add("Card.title")
        session_module.get_cache_store()["k"] = "v"

        assert session_module.get_instances() == {"Card_a": "instance"}
        assert session_module.get_dirtied() == {"Card.title"}
        assert session_module.get_cache_store() == {"k": "v"}


def test_default_getters_hand_back_throwaway_containers():
    """Mutating a default must not become the next caller's starting state."""
    session_module.get_instances()["leaked"] = object()
    session_module.get_dirtied().add("leaked")
    session_module.get_cache_store()["leaked"] = object()

    assert session_module.get_instances() == {}
    assert session_module.get_dirtied() == set()
    assert session_module.get_cache_store() == {}


def test_exit_clears_all_four_at_top_level():
    with session_module.request_scope():
        session_module.get_instances()["Card_a"] = "instance"
        session_module.get_dirtied().add("Card.title")
        session_module.get_cache_store()["k"] = "v"

    assert session_module.current_session() is None
    assert session_module.get_instances() == {}
    assert session_module.get_dirtied() == set()
    assert session_module.get_cache_store() == {}


def test_nested_scope_restores_the_outer_scope_not_the_global_default():
    with session_module.request_scope() as outer:
        session_module.get_instances()["outer"] = "o"
        session_module.get_dirtied().add("outer")
        session_module.get_cache_store()["outer"] = "o"
        outer.asset_paths.add("outer.css")

        with session_module.request_scope() as inner:
            assert inner is not outer
            assert session_module.current_session() is inner
            assert session_module.get_instances() == {}
            assert session_module.get_dirtied() == set()
            assert session_module.get_cache_store() == {}

            session_module.get_instances()["inner"] = "i"
            session_module.get_dirtied().add("inner")
            session_module.get_cache_store()["inner"] = "i"
            inner.asset_paths.add("inner.css")

        assert session_module.current_session() is outer
        assert session_module.get_instances() == {"outer": "o"}
        assert session_module.get_dirtied() == {"outer"}
        assert session_module.get_cache_store() == {"outer": "o"}
        assert outer.asset_paths == {"outer.css"}


def test_two_sequential_top_level_scopes_share_nothing():
    with session_module.request_scope() as first:
        session_module.get_instances()["first"] = "1"
        session_module.get_dirtied().add("first")
        session_module.get_cache_store()["first"] = "1"
        first.asset_paths.add("first.css")

    with session_module.request_scope() as second:
        assert second is not first
        assert second.asset_paths == set()
        assert session_module.get_instances() == {}
        assert session_module.get_dirtied() == set()
        assert session_module.get_cache_store() == {}


def test_exception_inside_the_block_still_resets_all_four():
    class Boom(Exception):
        pass

    try:
        with session_module.request_scope():
            session_module.get_instances()["Card_a"] = "instance"
            session_module.get_dirtied().add("Card.title")
            session_module.get_cache_store()["k"] = "v"
            raise Boom
    except Boom:
        pass

    assert session_module.current_session() is None
    assert session_module.get_instances() == {}
    assert session_module.get_dirtied() == set()
    assert session_module.get_cache_store() == {}


def test_exception_in_a_nested_scope_leaves_the_outer_scope_intact():
    class Boom(Exception):
        pass

    with session_module.request_scope() as outer:
        session_module.get_instances()["outer"] = "o"

        try:
            with session_module.request_scope():
                session_module.get_instances()["inner"] = "i"
                raise Boom
        except Boom:
            pass

        assert session_module.current_session() is outer
        assert session_module.get_instances() == {"outer": "o"}


def test_two_threads_do_not_see_each_others_scope_state():
    """ContextVars give each thread its own binding. Two concurrent scopes writing
    the same keys must each read back only their own writes."""
    start = threading.Barrier(2)
    mid = threading.Barrier(2)
    observed: dict[str, tuple[dict[str, object], dict[object, object]]] = {}
    errors: list[BaseException] = []

    def worker(name: str) -> None:
        try:
            with session_module.request_scope():
                start.wait(timeout=5)
                session_module.get_instances()[name] = name
                session_module.get_cache_store()[name] = name
                mid.wait(timeout=5)
                observed[name] = (
                    dict(session_module.get_instances()),
                    dict(session_module.get_cache_store()),
                )
        except BaseException as exc:  # noqa: BLE001 - surfaced on the main thread below
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=("a",)),
        threading.Thread(target=worker, args=("b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors, errors
    assert observed == {"a": ({"a": "a"}, {"a": "a"}), "b": ({"b": "b"}, {"b": "b"})}
    assert session_module.get_instances() == {}
    assert session_module.get_cache_store() == {}


def test_render_session_is_still_directly_constructible_with_autoescape_on():
    """render.py constructs a RenderSession directly and reads .jinja_env; growing
    the module must not force callers through request_scope."""
    session = session_module.RenderSession(template_dir="tests/templates")

    assert session.jinja_env.autoescape is True
    assert session.jinja_env.from_string("{{ v }}").render(v="<b>") == "&lt;b&gt;"
    assert session.asset_paths == set()


def test_scope_passes_template_dir_through_to_the_session():
    with session_module.request_scope(template_dir="tests/templates") as s:
        assert s.jinja_env.autoescape is True


def test_on_rendered_starts_empty_on_a_fresh_session():
    session = session_module.RenderSession(template_dir="tests/templates")

    assert session.on_rendered == []


def test_emit_rendered_calls_each_subscriber_in_registration_order():
    session = session_module.RenderSession(template_dir="tests/templates")
    calls: list[tuple[str, object, object]] = []
    # Plumbing only cares that emit_rendered forwards its args unchanged, so a
    # sentinel object stands in for a real BaseComponent/RenderedLevel here;
    # emit_rendered is typed against the real classes, so the sentinel needs
    # the cast to satisfy basedpyright.
    component = cast(Any, object())
    level = cast(Any, object())

    session.on_rendered.append(lambda c, lv: calls.append(("first", c, lv)))
    session.on_rendered.append(lambda c, lv: calls.append(("second", c, lv)))
    session.emit_rendered(component, level)

    assert calls == [("first", component, level), ("second", component, level)]


def test_emit_rendered_with_no_subscribers_is_a_no_op():
    session = session_module.RenderSession(template_dir="tests/templates")

    assert session.emit_rendered(cast(Any, object()), cast(Any, object())) is None


def test_emit_rendered_lets_a_subscriber_exception_propagate():
    """A broken subscriber is a bug in the subscriber, not something the spine
    hides; swallowing it would make a missing asset or a missing registry write
    look like a successful render."""

    class Boom(Exception):
        pass

    session = session_module.RenderSession(template_dir="tests/templates")
    reached: list[str] = []

    def explode(component: object, level: object) -> None:
        raise Boom

    session.on_rendered.append(explode)
    session.on_rendered.append(lambda c, lv: reached.append("after"))

    with pytest.raises(Boom):
        session.emit_rendered(cast(Any, object()), cast(Any, object()))
    assert reached == []


def test_each_scope_gets_its_own_subscriber_list():
    with session_module.request_scope(template_dir="tests/templates") as outer:
        outer.on_rendered.append(lambda c, lv: None)

        with session_module.request_scope(template_dir="tests/templates") as inner:
            assert inner.on_rendered == []
            inner.on_rendered.append(lambda c, lv: None)

        assert len(outer.on_rendered) == 1

    with session_module.request_scope(template_dir="tests/templates") as later:
        assert later.on_rendered == []
