"""request_scope's five ContextVars: fresh in, prior state out.

The five pieces of per-request mutable state (RenderSession asset slot, instance
registry, dirtied keys, cache store, cache reverse index) are the entire
ContextVar half of the mutable-state census. These tests pin the container
lifecycle - creation, nesting, exception cleanup, thread isolation - not any
read/write semantics, which land with the modules that consume them.
"""

import asyncio
import os
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


def test_render_session_registers_jinja_globals_alongside_the_builtins():
    def now() -> str:
        return "noon"

    session = session_module.RenderSession(jinja_globals={"now": now})
    assert session.jinja_env.globals["now"] is now
    # Updating rather than reassigning is the whole point: Jinja's own globals
    # must survive the addition.
    assert "range" in session.jinja_env.globals


def test_render_session_registers_jinja_filters_alongside_the_builtins():
    session = session_module.RenderSession(jinja_filters={"shout": str.upper})
    assert session.jinja_env.filters["shout"] is str.upper
    assert "upper" in session.jinja_env.filters


def test_render_session_still_constructs_with_no_arguments():
    session = session_module.RenderSession()
    assert session.jinja_env.autoescape is True
    assert "range" in session.jinja_env.globals
    assert "upper" in session.jinja_env.filters


def test_request_scope_applies_the_configured_globals_and_filters():
    """The default-construction branch is the only place settings are read, so
    an app that never builds its own session still gets its Jinja extras."""
    from pyjinhx.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx

    configure_pyjinhx(
        PjxSettings(jinja_globals={"x": 1}, jinja_filters={"shout": str.upper})
    )
    try:
        with session_module.request_scope() as session:
            assert session.jinja_env.globals["x"] == 1
            assert session.jinja_env.filters["shout"] is str.upper
            assert "range" in session.jinja_env.globals
    finally:
        shutdown_pyjinhx()


def test_request_scope_leaves_a_caller_supplied_session_alone():
    """A pre-built session is the caller's business — the FastAPI middleware
    builds its own and attaches hooks to it before the scope opens."""
    from pyjinhx.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx

    configure_pyjinhx(PjxSettings(jinja_globals={"x": 1}))
    prebuilt = session_module.RenderSession()
    try:
        with session_module.request_scope(session=prebuilt) as session:
            assert session is prebuilt
            assert "x" not in session.jinja_env.globals
    finally:
        shutdown_pyjinhx()


def test_render_session_configured_global_fires_in_rendered_output():
    """Membership in .globals is not the contract — being callable from a
    template is. This renders the global rather than inspecting the dict."""

    def site_name() -> str:
        return "pyjinhx"

    session = session_module.RenderSession(jinja_globals={"site_name": site_name})
    template = session.jinja_env.from_string("{{ site_name() }}")

    assert template.render() == "pyjinhx"


def test_render_session_configured_filter_fires_in_rendered_output():
    session = session_module.RenderSession(jinja_filters={"shout": str.upper})
    template = session.jinja_env.from_string("{{ 'ok'|shout }}")

    assert template.render() == "OK"


def test_render_session_configured_filter_does_not_clobber_builtin_in_rendered_output():
    """update() vs assignment, proven through output: |upper is Jinja's own
    filter and must keep working next to the one the caller added."""
    session = session_module.RenderSession(jinja_filters={"shout": str.upper})
    template = session.jinja_env.from_string("{{ 'ok'|shout }}|{{ 'b'|upper }}")

    assert template.render() == "OK|B"


def test_render_session_with_no_extras_still_renders_jinja_builtins():
    """The None default is 'nothing to add', not 'clear' — a session built with
    no configuration renders the standard library normally."""
    session = session_module.RenderSession()
    template = session.jinja_env.from_string("{{ 'b'|upper }}{{ range(3)|list }}")

    assert template.render() == "B[0, 1, 2]"


def test_request_scope_default_session_seeded_from_settings_renders_configured_global_and_filter():
    """The no-session branch is the only place settings are read, and reaching
    them has to survive all the way into a rendered template — not just into
    the environment's dicts."""
    from pyjinhx.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx

    def site_name() -> str:
        return "pyjinhx"

    configure_pyjinhx(
        PjxSettings(
            jinja_globals={"site_name": site_name},
            jinja_filters={"shout": str.upper},
        )
    )
    try:
        with session_module.request_scope() as session:
            template = session.jinja_env.from_string(
                "{{ site_name() }}|{{ 'ok'|shout }}|{{ 'b'|upper }}"
            )
            assert template.render() == "pyjinhx|OK|B"
    finally:
        shutdown_pyjinhx()


def test_request_scope_with_unset_settings_still_renders_jinja_builtins():
    """jinja_globals/jinja_filters default to None; the seeding branch must
    hand those straight through without disturbing the environment."""
    from pyjinhx.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx

    configure_pyjinhx(PjxSettings())
    try:
        with session_module.request_scope() as session:
            template = session.jinja_env.from_string(
                "{{ 'b'|upper }}{{ range(3)|list }}"
            )
            assert template.render() == "B[0, 1, 2]"
    finally:
        shutdown_pyjinhx()


def test_environment_for_reuses_one_environment_per_settings_instance():
    """The whole point of the hoist: every request served under one settings
    object shares one environment, so Jinja's template cache survives the
    request that filled it."""
    from pyjinhx.config import PjxSettings

    settings = PjxSettings(jinja_globals={"x": 1})

    first = session_module._environment_for(settings)
    second = session_module._environment_for(settings)

    assert first is second


def test_environment_for_does_not_share_across_value_equal_settings():
    """PjxSettings is a frozen dataclass, so two distinct instances compare
    equal — identity, not equality, is what the cache keys on. Two apps in one
    process must never end up updating each other's environment."""
    from pyjinhx.config import PjxSettings

    one = PjxSettings()
    two = PjxSettings()

    assert one == two
    assert session_module._environment_for(one) is not session_module._environment_for(
        two
    )


def test_environment_for_keeps_each_settings_extras_to_itself():
    from pyjinhx.config import PjxSettings

    left = PjxSettings(jinja_globals={"left": 1}, jinja_filters={"lshout": str.upper})
    right = PjxSettings(jinja_globals={"right": 2}, jinja_filters={"rshout": str.lower})

    left_env = session_module._environment_for(left)
    right_env = session_module._environment_for(right)

    assert left_env is not right_env
    assert left_env.globals["left"] == 1
    assert "right" not in left_env.globals
    assert "rshout" not in left_env.filters
    assert right_env.globals["right"] == 2
    assert "left" not in right_env.globals
    assert "lshout" not in right_env.filters


def test_environment_for_does_not_reapply_the_extras_on_a_cache_hit():
    """A cache hit must return the stored environment untouched: no second
    construction, and no second .update() that would resurrect a name the app
    deliberately removed after startup."""
    from pyjinhx.config import PjxSettings

    settings = PjxSettings(jinja_globals={"x": 1}, jinja_filters={"shout": str.upper})

    env = session_module._environment_for(settings)
    globals_before = env.globals
    del env.globals["x"]
    del env.filters["shout"]

    again = session_module._environment_for(settings)

    assert again is env
    assert again.globals is globals_before
    assert "x" not in again.globals
    assert "shout" not in again.filters


def test_environment_for_is_safe_under_concurrent_first_lookups():
    """Two threads racing the first _environment_for(settings) call for the
    same settings instance (e.g. two sync FastAPI handlers dispatched into
    Starlette's threadpool) must not each build-and-store their own
    Environment — the lock is what makes 'one environment per settings' hold
    under real concurrency, not just in a single-threaded test."""
    from pyjinhx.config import PjxSettings

    settings = PjxSettings(jinja_globals={"x": 1})
    start = threading.Barrier(8)
    results: list[session_module.Environment] = []
    lock = threading.Lock()

    def worker() -> None:
        start.wait(timeout=5)
        env = session_module._environment_for(settings)
        with lock:
            results.append(env)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert len(results) == 8
    assert len({id(env) for env in results}) == 1


def test_cached_environment_keeps_the_loader_autoescape_and_builtins():
    """Reuse changes nothing about how the environment is built: same loader,
    same autoescape, and Jinja's own standard library still resolves next to
    the configured extras."""
    from pyjinhx.config import PjxSettings

    settings = PjxSettings(jinja_globals={"x": 1}, jinja_filters={"shout": str.upper})

    env = session_module._environment_for(settings)

    assert isinstance(env.loader, session_module.AbsolutePathLoader)
    assert env.autoescape is True
    template = env.from_string(
        "{{ x }}|{{ 'ok'|shout }}|{{ 'b'|upper }}|{{ range(2)|list }}"
        "|{{ 'ab'|length }}|{{ 'ab' is string }}"
    )
    assert template.render() == "1|OK|B|[0, 1]|2|True"


def test_render_session_adopts_a_supplied_environment():
    from pyjinhx.config import PjxSettings

    env = session_module._environment_for(PjxSettings(jinja_globals={"x": 1}))
    session = session_module.RenderSession(jinja_env=env)

    assert session.jinja_env is env


def test_render_session_rejects_an_adopted_environment_with_extras():
    """An adopted environment is shared with every other session on the same
    settings; updating it here would leak one session's names into all of them."""
    from pyjinhx.config import PjxSettings

    env = session_module._environment_for(PjxSettings())

    with pytest.raises(TypeError):
        session_module.RenderSession(jinja_env=env, jinja_globals={"x": 1})

    with pytest.raises(TypeError):
        session_module.RenderSession(jinja_env=env, jinja_filters={"shout": str.upper})


def test_request_scope_default_session_uses_the_cached_environment():
    """Two requests under one configuration must land on one environment —
    otherwise every request starts with an empty template cache."""
    from pyjinhx.config import (
        PjxSettings,
        configure_pyjinhx,
        current_settings,
        shutdown_pyjinhx,
    )

    configure_pyjinhx(PjxSettings(jinja_globals={"x": 1}))
    try:
        expected = session_module._environment_for(current_settings())
        with session_module.request_scope() as first:
            pass
        with session_module.request_scope() as second:
            pass

        assert first.jinja_env is expected
        assert second.jinja_env is expected
        assert first is not second
    finally:
        shutdown_pyjinhx()


def test_environment_for_picks_up_template_edits_across_renders(tmp_path):
    """The environment now outlives the request that built it, and Jinja's
    template cache lives on the environment — so the only thing standing
    between a developer editing a template and the server serving the old one
    forever is AbsolutePathLoader.get_source's uptodate() mtime closure. This
    pins that closure through the cached environment: same Environment object,
    same warm cache, edited file, new output."""
    from pyjinhx.config import PjxSettings

    template_path = tmp_path / "hot.html"
    template_path.write_text("<p>before</p>", encoding="utf-8")
    settings = PjxSettings()
    env = session_module._environment_for(settings)
    session = session_module.RenderSession(jinja_env=env)

    assert session.jinja_env is env
    assert session.jinja_env.get_template(str(template_path)).render() == (
        "<p>before</p>"
    )

    # Without this the rest of the test is vacuous: if the environment's cache
    # were cold, a second get_template would recompile anyway and picking up
    # the edit would prove nothing about invalidation.
    warm = env.get_template(str(template_path))
    assert env.get_template(str(template_path)) is warm

    template_path.write_text("<p>after</p>", encoding="utf-8")
    # Explicit mtime bump: a coarse-resolution filesystem can stamp both writes
    # with the same st_mtime, which would make uptodate() report "unchanged"
    # for reasons that have nothing to do with the code under test.
    stat = template_path.stat()
    os.utime(template_path, (stat.st_atime + 10, stat.st_mtime + 10))

    reloaded = env.get_template(str(template_path))

    assert env is session_module._environment_for(settings)
    assert reloaded is not warm
    assert reloaded.render() == "<p>after</p>"


def test_freshness_cache_is_empty_outside_any_scope():
    """An unset freshness cache reads as an empty dict, never raises: callers
    outside a request degrade to no memoization rather than crashing."""
    assert session_module.get_freshness_cache() == {}


def test_freshness_cache_is_one_object_for_the_life_of_a_scope():
    """The fan-out threadpool copies the caller's Context per work item, so every
    worker must land on the same dict object request_scope() bound."""
    with session_module.request_scope():
        first = session_module.get_freshness_cache()
        first["/tmp/a.html"] = True
        assert session_module.get_freshness_cache() is first

    with session_module.request_scope():
        assert session_module.get_freshness_cache() == {}


def test_nested_scope_restores_the_outer_freshness_cache():
    with session_module.request_scope():
        session_module.get_freshness_cache()["/tmp/outer.html"] = True

        with session_module.request_scope():
            assert session_module.get_freshness_cache() == {}
            session_module.get_freshness_cache()["/tmp/inner.html"] = True

        assert session_module.get_freshness_cache() == {"/tmp/outer.html": True}

    assert session_module.get_freshness_cache() == {}


def test_uptodate_records_and_then_short_circuits_within_one_request():
    """The freshness closure confirms a path once per request, then answers from
    the cache: this is the memoization walk_manifest's repeat lookups ride on."""
    template_path = _TEMPLATE_DIR / "plain_div.html"
    loader = session_module.AbsolutePathLoader()
    env = session_module.Environment(loader=loader)

    with session_module.request_scope():
        _source, filename, uptodate = loader.get_source(env, str(template_path))
        assert session_module.get_freshness_cache() == {}

        assert uptodate() is True
        assert session_module.get_freshness_cache() == {filename: True}

        # Second call must not consult the filesystem at all: a stat() that would
        # raise proves the answer came from the request cache.
        def _boom(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("uptodate() re-stat'ed a confirmed-fresh path")

        original_stat = Path.stat
        Path.stat = _boom  # type: ignore[method-assign]
        try:
            assert uptodate() is True
        finally:
            Path.stat = original_stat  # type: ignore[method-assign]

    # A new request starts cold, so a mid-request edit is seen on the next one.
    with session_module.request_scope():
        assert session_module.get_freshness_cache() == {}
