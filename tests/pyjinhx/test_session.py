"""request_scope's five ContextVars: fresh in, prior state out.

The five pieces of per-request mutable state (RenderSession asset slot, instance
registry, dirtied keys, cache store, cache reverse index) are the entire
ContextVar half of the mutable-state census. These tests pin the container
lifecycle - creation, nesting, exception cleanup, thread isolation - not any
read/write semantics, which land with the modules that consume them.
"""

import asyncio
import threading
from pathlib import Path
from typing import Any, cast

import pytest

from pyjinhx import session as session_module
from pyjinhx._component import BaseComponent
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.rendering import render

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


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
    session = session_module.RenderSession()

    assert session.jinja_env.autoescape is True
    assert session.jinja_env.from_string("{{ v }}").render(v="<b>") == "&lt;b&gt;"
    assert session.asset_paths == set()


def test_scope_builds_a_session_with_the_absolute_path_loader():
    with session_module.request_scope() as s:
        assert isinstance(s.jinja_env.loader, session_module.AbsolutePathLoader)


def test_passing_template_dir_is_now_a_type_error():
    with pytest.raises(TypeError):
        session_module.RenderSession(template_dir="tests/templates")  # type: ignore[call-arg]

    with (
        pytest.raises(TypeError),
        session_module.request_scope(template_dir="tests/templates"),  # type: ignore[call-arg]
    ):
        pass


class PlainBox(BaseComponent):
    """Component rendered against a hand-built descriptor, not MRO discovery."""


# There is no `__pjx_template__` override attribute anywhere in pyjinhx —
# template resolution is a pure MRO/filesystem walk (`class_name.pjx` beside
# the defining module; see _component.py's `_walk_template`). This test needs a
# specific template, so it bypasses that walk entirely, the same way
# test_render_level.py does: build a ClassDescriptor by hand and assign it.
PlainBox.__pjx_descriptor__ = ClassDescriptor(
    template_path=_TEMPLATE_DIR / "plain_div.html",
    slot_fields=frozenset(),
    children_field=None,
    css_paths=(),
    js_paths=(),
    strict=True,
    provenance={"template": PlainBox},
)


def test_on_rendered_fires_once_per_render(render_session):
    seen = []
    render_session.on_rendered.append(
        lambda component, level, session: seen.append(component)
    )
    box = PlainBox()
    render(box, render_session)
    assert seen == [box]


def test_on_rendered_receives_the_rendered_level(render_session):
    captured = []
    render_session.on_rendered.append(
        lambda component, level, session: captured.append(level)
    )
    render(PlainBox(), render_session)
    assert captured[0].descriptor is PlainBox.__pjx_descriptor__


def test_on_rendered_starts_empty_on_a_fresh_session():
    session = session_module.RenderSession()

    assert session.on_rendered == []


def test_emit_rendered_calls_each_subscriber_in_registration_order():
    session = session_module.RenderSession()
    calls: list[tuple[str, object, object]] = []
    # Plumbing only cares that emit_rendered forwards its args unchanged, so a
    # sentinel object stands in for a real BaseComponent/RenderedLevel here;
    # emit_rendered is typed against the real classes, so the sentinel needs
    # the cast to satisfy basedpyright.
    component = cast(Any, object())
    level = cast(Any, object())

    session.on_rendered.append(lambda c, lv, s: calls.append(("first", c, lv)))
    session.on_rendered.append(lambda c, lv, s: calls.append(("second", c, lv)))
    session.emit_rendered(component, level)

    assert calls == [("first", component, level), ("second", component, level)]


def test_emit_rendered_with_no_subscribers_is_a_no_op():
    session = session_module.RenderSession()

    assert session.emit_rendered(cast(Any, object()), cast(Any, object())) is None


def test_emit_rendered_lets_a_subscriber_exception_propagate():
    """A broken subscriber is a bug in the subscriber, not something the spine
    hides; swallowing it would make a missing asset or a missing registry write
    look like a successful render."""

    class Boom(Exception):
        pass

    session = session_module.RenderSession()
    reached: list[str] = []

    def explode(component: object, level: object, session: object) -> None:
        raise Boom

    session.on_rendered.append(explode)
    session.on_rendered.append(lambda c, lv, s: reached.append("after"))

    with pytest.raises(Boom):
        session.emit_rendered(cast(Any, object()), cast(Any, object()))
    assert reached == []


def test_each_scope_gets_its_own_subscriber_list():
    with session_module.request_scope() as outer:
        outer.on_rendered.append(lambda c, lv, s: None)

        with session_module.request_scope() as inner:
            assert inner.on_rendered == []
            inner.on_rendered.append(lambda c, lv, s: None)

        assert len(outer.on_rendered) == 1

    with session_module.request_scope() as later:
        assert later.on_rendered == []


def test_add_dirtied_updates_the_active_scopes_set():
    with session_module.request_scope():
        session_module.add_dirtied({"todos"})
        session_module.add_dirtied(["todos", "user"])
        assert session_module.get_dirtied() == {"todos", "user"}


def test_add_dirtied_outside_a_scope_is_a_no_op():
    session_module.add_dirtied({"todos"})
    assert session_module.get_dirtied() == set()


def test_session_starts_with_no_runtime_injected():
    session = session_module.RenderSession()
    assert session.runtime_injected is False
    assert session.runtime_script is None


def test_cache_reverse_is_empty_outside_a_request_scope():
    from pyjinhx.session import get_cache_reverse

    assert get_cache_reverse() == {}


def test_cache_reverse_is_fresh_per_request_scope():
    from pyjinhx.session import get_cache_reverse, request_scope

    with request_scope():
        get_cache_reverse()["todos"] = {(int, 1)}
        assert get_cache_reverse() == {"todos": {(int, 1)}}
    with request_scope():
        assert get_cache_reverse() == {}


def test_get_load_context_is_none_outside_any_scope():
    """Reading the app context outside a request is a miss, not a LookupError."""
    assert session_module.get_load_context() is None


def test_concurrent_scopes_never_see_each_others_load_context():
    """Two overlapping requests are two asyncio tasks, and a task gets its own
    copy of the ContextVar map - so interleaving must not cross the values.

    Run via asyncio.run() inside a dedicated thread, not a `@pytest.mark.anyio`
    coroutine on the main thread: pytest-playwright's browser fixtures leave
    asyncio's running-loop flag permanently set on the main thread for the rest
    of the session (a known pytest-playwright/asyncio interaction, unrelated to
    this ContextVar mechanism), which makes any later asyncio.run() there raise
    "cannot run the event loop while another loop is running". The flag is
    thread-local, so a fresh OS thread gets a clean slate; ContextVar task
    isolation - what this test actually pins - is unaffected by which thread
    hosts the loop.
    """

    async def run(label: str, first_sleep: float, second_sleep: float) -> list[object]:
        seen: list[object] = []
        await asyncio.sleep(first_sleep)
        with session_module.request_scope(load_context=label):
            seen.append(session_module.get_load_context())
            await asyncio.sleep(second_sleep)
            seen.append(session_module.get_load_context())
        seen.append(session_module.get_load_context())
        return seen

    async def main() -> tuple[list[object], list[object]]:
        return await asyncio.gather(
            run("left", 0.0, 0.02),
            run("right", 0.01, 0.0),
        )

    results: dict[str, tuple[list[object], list[object]]] = {}

    def worker() -> None:
        results["value"] = asyncio.run(main())

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    left, right = results["value"]
    assert left == ["left", "left", None]
    assert right == ["right", "right", None]


def test_request_scope_binds_the_load_context_it_was_given():
    sentinel = object()
    with session_module.request_scope(load_context=sentinel):
        assert session_module.get_load_context() is sentinel

    assert session_module.get_load_context() is None


def test_request_scope_without_load_context_leaves_it_none():
    """Existing non-DI callers must see no behaviour change."""
    with session_module.request_scope():
        assert session_module.get_load_context() is None

    assert session_module.get_load_context() is None


def test_explicit_none_load_context_does_not_shadow_an_outer_value():
    """`load_context=None` means "not supplied", so a nested scope that omits it
    keeps reading the enclosing request's value rather than blanking it."""
    outer = object()
    with session_module.request_scope(load_context=outer):
        with session_module.request_scope(load_context=None):
            assert session_module.get_load_context() is outer

        assert session_module.get_load_context() is outer


def test_nested_load_context_restores_the_outer_value_on_exit():
    outer = object()
    inner = object()
    with session_module.request_scope(load_context=outer):
        with session_module.request_scope(load_context=inner):
            assert session_module.get_load_context() is inner

        assert session_module.get_load_context() is outer

    assert session_module.get_load_context() is None


def test_exception_inside_the_block_still_resets_load_context():
    class Boom(Exception):
        pass

    try:
        with session_module.request_scope(load_context=object()):
            raise Boom
    except Boom:
        pass

    assert session_module.get_load_context() is None
