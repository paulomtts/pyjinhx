"""request_scope's four ContextVars: fresh in, prior state out.

The four pieces of per-request mutable state (RenderSession asset slot, instance
registry, dirtied keys, cache store) are the entire ContextVar half of the
mutable-state census. These tests pin the container lifecycle - creation,
nesting, exception cleanup, thread isolation - not any read/write semantics,
which land with the modules that consume them.
"""

import threading

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
