"""Tests for RenderSession's Jinja environment, configured extras, freshness cache and quiet collisions."""

import os
import threading
from pathlib import Path

import pytest

from pyjinhx.rendering import session as session_module
from tests.unit.rendering.session._session_helpers import _TEMPLATE_DIR


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


def test_freshness_cache_does_not_leak_across_request_scopes(tmp_path):
    """The memoized "fresh" verdict is a per-request shortcut, not a per-process
    one: a template edited between two requests must be re-stat'ed by the
    second. Scope 2 starts on an empty dict, so uptodate() has nothing to trust
    and has to ask the filesystem again."""
    from pyjinhx.config import PjxSettings

    template_path = tmp_path / "across.html"
    template_path.write_text("<p>before</p>", encoding="utf-8")
    # One settings instance for both scopes: _environment_for memoizes per
    # instance, so this pins the same Environment - and the same warm Jinja
    # template cache - across the two requests. A fresh Environment in scope 2
    # would recompile regardless and prove nothing about the freshness cache.
    settings = PjxSettings()
    env = session_module._environment_for(settings)

    with session_module.request_scope():
        assert env.get_template(str(template_path)).render() == "<p>before</p>"
        # Warm: uptodate() is only ever invoked on a cache *hit* (Jinja's
        # is_up_to_date check), never on the first, cache-miss load. Without
        # this second call inside scope 1, the freshness dict is never written
        # to in the first place - there would be nothing to leak, and the
        # "revert #890" probe below would pass for the wrong reason (verified:
        # omitting this line makes the RED step in 1.3 stay green).
        assert env.get_template(str(template_path)).render() == "<p>before</p>"

    template_path.write_text("<p>after</p>", encoding="utf-8")
    # Explicit mtime bump: a coarse-resolution filesystem can stamp both writes
    # with the same st_mtime, which would make uptodate() report "unchanged"
    # for reasons that have nothing to do with the code under test.
    stat = template_path.stat()
    os.utime(template_path, (stat.st_atime + 10, stat.st_mtime + 10))

    with session_module.request_scope():
        assert env.get_template(str(template_path)).render() == "<p>after</p>"


def test_uptodate_records_and_then_short_circuits_within_one_request():
    """The freshness closure confirms a path once per request, then answers from
    the cache: this is the memoization walk_manifest's repeat lookups ride on."""
    template_path = _TEMPLATE_DIR / "basic/plain_div.html"
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


def test_quiet_collisions_read_as_an_empty_set_outside_any_scope():
    """An unset quiet set reads as an empty frozenset, never raises: a caller
    outside a request degrades to "nothing is quieted", which is the loud
    default register_instance() had before the set existed."""
    assert session_module.get_quiet_collisions() == frozenset()


def test_request_scope_binds_an_empty_quiet_set():
    with session_module.request_scope():
        assert session_module.get_quiet_collisions() == frozenset()


def test_nested_scope_restores_the_outer_quiet_set():
    """An inner request starts with nothing quieted and hands the outer request
    its own set back — a suppression is one request's claim, never a sibling's."""
    with session_module.request_scope():
        session_module._quiet_collisions.set(frozenset({"Widget_outer"}))

        with session_module.request_scope():
            assert session_module.get_quiet_collisions() == frozenset()
            session_module._quiet_collisions.set(frozenset({"Widget_inner"}))

        assert session_module.get_quiet_collisions() == frozenset({"Widget_outer"})

    assert session_module.get_quiet_collisions() == frozenset()


def test_exception_inside_the_block_still_resets_the_quiet_set():
    with pytest.raises(RuntimeError, match="boom"), session_module.request_scope():
        session_module._quiet_collisions.set(frozenset({"Widget_w1"}))
        raise RuntimeError("boom")

    assert session_module.get_quiet_collisions() == frozenset()


def test_two_threads_do_not_see_each_others_quiet_set():
    """The fan-out pass opens its quiet block inside a pool worker, so a worker's
    set must not be visible to any other thread that never opened one."""
    seen: dict[str, frozenset[str]] = {}

    def quieting() -> None:
        with session_module.request_scope():
            session_module._quiet_collisions.set(frozenset({"Widget_a"}))
            seen["quieting"] = session_module.get_quiet_collisions()

    def bystander() -> None:
        with session_module.request_scope():
            seen["bystander"] = session_module.get_quiet_collisions()

    first = threading.Thread(target=quieting)
    first.start()
    first.join()
    second = threading.Thread(target=bystander)
    second.start()
    second.join()

    assert seen["quieting"] == frozenset({"Widget_a"})
    assert seen["bystander"] == frozenset()
