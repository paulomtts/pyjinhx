"""Composition tests: compose() joins the primary body with the OOB fragments."""

import dataclasses
from typing import Annotated

import pytest

from pyjinhx import discovery, registry
from pyjinhx.reactive import cache
from pyjinhx.reactive.cache import cache_get, cache_has, cache_put
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.reactive.root_attrs import stamp_reactive_root_attrs
from pyjinhx.responses import PjxResponse, compose
from pyjinhx.session import RenderSession, add_dirtied, request_scope

LOAD_CALLS: list[str | None] = []


class ResponseWidget(ReactiveComponent, react=("todos",)):
    """A reactive component keyed by ``pjx_key``, dirtied by the ``todos`` key."""

    pjx_key: Annotated[str, PjxKey()] = ""
    data: str = ""

    @classmethod
    def load(cls, pjx_key: str) -> "ResponseWidget":
        LOAD_CALLS.append(pjx_key)
        return cls(pjx_key=pjx_key, data=f"data:{pjx_key}")


class SidebarWidget(ReactiveComponent, react=("sidebar",)):
    """A nested reactive region no `todos` mutation ever touches."""


class ShellWidget(ReactiveComponent, react=("todos",)):
    """A dirty parent whose template nests a disjoint reactive region."""

    @classmethod
    def load(cls) -> "ShellWidget":
        return cls()


@pytest.fixture(autouse=True)
def _publish_registry(tmp_path, monkeypatch):
    """Publish a tag -> class map for ResponseWidget and point it at a real template."""
    LOAD_CALLS.clear()
    template = tmp_path / "response_widget.pjx"
    template.write_text("<div>{{ pjx_key }}</div>")
    sidebar = tmp_path / "sidebar_widget.pjx"
    sidebar.write_text("<aside>sidebar</aside>")
    shell = tmp_path / "shell_widget.pjx"
    shell.write_text('<div><SidebarWidget id="side"/></div>')
    discovery.build_registry(tmp_path, [ResponseWidget, SidebarWidget, ShellWidget])
    # `_resolve_template_path` probes the class's defining module directory, not the
    # dir passed to build_registry; repoint the descriptor at the tmp_path file. The
    # loader is absolute-only, so the descriptor carries the full path.
    ResponseWidget.__pjx_descriptor__ = dataclasses.replace(
        ResponseWidget.__pjx_descriptor__, template_path=template
    )
    SidebarWidget.__pjx_descriptor__ = dataclasses.replace(
        SidebarWidget.__pjx_descriptor__, template_path=sidebar
    )
    ShellWidget.__pjx_descriptor__ = dataclasses.replace(
        ShellWidget.__pjx_descriptor__, template_path=shell
    )
    yield


def entry(instance_id: str, load: object = None, hash_: str = "stale") -> dict:
    """Build one synthetic X-PJX-Mounted manifest entry for ResponseWidget."""
    return {
        "type": "response_widget",
        "id": instance_id,
        "load": load,
        "hash": hash_,
    }


def mounted_entry(instance_id: str, load: object = None, hash_: str = "stale") -> dict:
    """Alias for `entry()`, named to match the plan's Task 6 test bodies."""
    return entry(instance_id, load=load, hash_=hash_)


def _compose(result: object, *, session: RenderSession | None = None) -> PjxResponse:
    """`compose()` narrowed to its non-passthrough return, for tests that read
    `.body`/`.headers` off the result — every case here composes a real body."""
    composed = compose(result, session=session)
    assert isinstance(composed, PjxResponse)
    return composed


def test_no_dirtied_and_no_mounted_leaves_primary_untouched():
    with request_scope() as session:
        composed = _compose("<p>hello</p>", session=session)
        assert composed.body == "<p>hello</p>"


def test_dirty_mounted_region_appends_an_oob_fragment_after_the_primary():
    with request_scope() as session:
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        session.pjx_mounted = [entry("a", load="todo-1")]
        body = _compose("<p>hello</p>", session=session).body
        assert body.startswith("<p>hello</p>")
        assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in body


def test_absent_primary_yields_oob_fragments_only():
    with request_scope() as session:
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        session.pjx_mounted = [entry("a", load="todo-1")]
        body = _compose(None, session=session).body
        assert body.startswith("<div")
        assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in body


def test_region_already_in_the_primary_is_not_swapped_again():
    with request_scope() as session:
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        session.pjx_mounted = [entry("a", load="todo-1")]
        primary = '<div data-pjx-id="a">fresh</div>'
        composed = _compose(primary, session=session)
        assert composed.body == primary
        assert "hx-swap-oob" not in composed.body


def test_malformed_mounted_header_degrades_to_primary_only():
    with request_scope() as session:
        add_dirtied(["todos"])
        session.pjx_mounted = []
        composed = _compose("<p>hello</p>", session=session)
        assert composed.body == "<p>hello</p>"


def test_a_parsed_manifest_entry_fans_out():
    """The manifest arrives already parsed into a list; compose() never sees JSON."""
    with request_scope() as session:
        add_dirtied(["todos"])
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        session.pjx_mounted = [entry("a", load="1")]
        body = _compose("", session=session).body
    assert "outerHTML:[data-pjx-id='a']" in body


@pytest.mark.parametrize("mounted", [[]])
def test_absent_manifest_leaves_the_primary_untouched(mounted):
    with request_scope() as session:
        add_dirtied(["todos"])
        session.pjx_mounted = mounted
        composed = _compose("<p>x</p>", session=session)
        assert composed.body == "<p>x</p>"


def test_primary_only_response_sets_no_headers():
    with request_scope() as session:
        composed = _compose("<p>hello</p>", session=session)
        assert composed.headers == {}


def test_primary_plus_oob_fragments_sets_no_headers():
    with request_scope() as session:
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        session.pjx_mounted = [entry("a", load="todo-1")]
        composed = _compose("<p>hello</p>", session=session)
        assert "hx-swap-oob" in composed.body
        assert composed.headers == {}


def test_oob_only_response_sets_reswap_none():
    with request_scope() as session:
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        session.pjx_mounted = [entry("a", load="todo-1")]
        composed = _compose(None, session=session)
        assert "hx-swap-oob" in composed.body
        assert composed.headers == {"HX-Reswap": "none"}


def test_empty_response_sets_reswap_none():
    with request_scope() as session:
        composed = _compose(None, session=session)
        assert composed.body == ""
        assert composed.headers == {"HX-Reswap": "none"}


def test_whitespace_only_primary_counts_as_no_primary():
    with request_scope() as session:
        composed = _compose("   \n\t ", session=session)
        assert composed.headers == {"HX-Reswap": "none"}


def test_a_dirtied_key_evicts_its_cache_entry_so_the_region_re_renders():
    """A cached load result for a dirtied key must not answer "clean"."""
    with request_scope() as session:
        cache_put(ResponseWidget, "1", "stale-payload", react_keys=("todos",))
        registry.register_instance(ResponseWidget.__name__, "a", "entry")
        add_dirtied(["todos"])
        session.pjx_mounted = [mounted_entry("a", load="1")]
        composed = _compose("", session=session)
        assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in composed.body
        # The re-load runs on fanout's threadpool, but the worker runs inside
        # a copy of this request's context, so cache_put()'s write during that
        # reload lands back in this thread's store.
        assert cache_has(ResponseWidget, "1") is True  # re-loaded, not left evicted


def test_an_undirtied_cache_entry_survives_the_fan_out():
    """Eviction is scoped to the dirtied keys; unrelated entries stay cached."""
    with request_scope() as session:
        cache_put(ResponseWidget, "1", "payload", react_keys=("other",))
        add_dirtied(["todos"])
        session.pjx_mounted = []
        compose("", session=session)
        assert cache_get(ResponseWidget, "1") == "payload"


def test_calling_compose_twice_reinvalidates_and_reloads_each_time(monkeypatch):
    """Each `compose()` call re-runs invalidation and reload for dirtied keys."""
    calls: list[set[str]] = []
    original = cache.invalidate
    monkeypatch.setattr(
        cache, "invalidate", lambda keys: (calls.append(set(keys)), original(keys))[1]
    )
    with request_scope() as session:
        registry.register_instance(ResponseWidget.__name__, "a", "entry")
        session.pjx_mounted = [mounted_entry("a", load="1")]
        add_dirtied(["todos"])
        compose("", session=session)
        add_dirtied(["todos"])
        compose("", session=session)
    assert all("todos" in seen for seen in calls)
    assert LOAD_CALLS == ["1", "1"]


def test_a_dynamic_dirty_key_evicts_the_instance_it_names():
    """#488's other deferred half: dynamic keys must reach the cache, not just fan-out.

    `@mutates(..., key=...)` / `dirty(reactive_key(KEY, arg))` dirty *only* the
    composite ``"todos:1"`` form (see `mutations.py`) — never the bare static key
    alongside it. Populate the cache through a real `.load()` call, so the entry
    is indexed exactly the way `_wrap_load` indexes it in production — under both
    the bare and the composite form — which is the one path this test is meant
    to exercise.
    """
    with request_scope() as session:
        registry.register_instance(ResponseWidget.__name__, "a", "entry")
        ResponseWidget.load("1")
        add_dirtied(["todos:1"])
        session.pjx_mounted = [mounted_entry("a", load="1")]
        composed = _compose("", session=session)
        assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in composed.body


def test_candidates_is_empty_without_mounted_or_dirtied():
    """Nothing mounted and nothing dirtied means there is nothing to fan out to."""
    with request_scope() as session:
        composed = _compose("<p>hello</p>", session=session)
        assert "hx-swap-oob" not in composed.body


def test_candidates_is_empty_when_mounted_but_nothing_dirtied():
    """A mounted region only becomes a candidate once a key it reacts to is dirtied."""
    with request_scope() as session:
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        session.pjx_mounted = [entry("a", load="todo-1")]
        composed = _compose("<p>hello</p>", session=session)
        assert "hx-swap-oob" not in composed.body


def test_candidates_is_empty_when_dirtied_but_nothing_mounted():
    """A dirtied key with an empty manifest has no region to swap."""
    with request_scope() as session:
        add_dirtied(["todos"])
        composed = _compose("<p>hello</p>", session=session)
        assert "hx-swap-oob" not in composed.body


def test_two_dirty_regions_each_get_exactly_one_fragment_in_manifest_order():
    """Every dirtied, mounted region is swapped once, in the order the client sent."""
    with request_scope() as session:
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        registry.register_instance(ResponseWidget.__name__, "b", "resolved-entry")
        add_dirtied(["todos"])
        session.pjx_mounted = [entry("a", load="todo-1"), entry("b", load="todo-2")]
        body = _compose("<p>hello</p>", session=session).body

        first = "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\""
        second = "hx-swap-oob=\"outerHTML:[data-pjx-id='b']\""
        assert body.count(first) == 1
        assert body.count(second) == 1
        assert body.index(first) < body.index(second)
        assert body.index("<p>hello</p>") < body.index(first)


def test_fan_out_follows_manifest_order():
    """The OOB legs mirror manifest order, which is what fixes fragment order."""
    with request_scope() as session:
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        registry.register_instance(ResponseWidget.__name__, "b", "resolved-entry")
        add_dirtied(["todos"])
        session.pjx_mounted = [entry("b", load="todo-2"), entry("a", load="todo-1")]
        body = _compose("", session=session).body
        first = "hx-swap-oob=\"outerHTML:[data-pjx-id='b']\""
        second = "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\""
        assert body.index(first) < body.index(second)


def test_compose_outside_a_request_scope_composes_the_primary_only():
    """The session lookup degrades to a bare session rather than raising with no scope."""
    assert _compose("<p>hello</p>").body == "<p>hello</p>"


def test_none_and_empty_string_primary_compose_the_same_empty_body():
    """A ``None`` or empty-string primary both compose to an empty body."""
    with request_scope() as session:
        assert _compose(None, session=session).body == ""
        assert _compose("", session=session).body == ""


def test_plain_string_and_markup_primary_compose_identically():
    """`Markup()` adopts a plain str as-is (no escaping); handlers must escape upstream."""
    from markupsafe import Markup

    with request_scope() as session:
        assert _compose("<p>hi</p>", session=session).body == "<p>hi</p>"
        assert _compose(Markup("<p>hi</p>"), session=session).body == "<p>hi</p>"


def test_primary_with_dunder_html_is_used_as_markup():
    """An object exposing `__html__` is adopted by `Markup()` without escaping."""

    class Fragment:
        def __html__(self) -> str:
            return "<p>hi</p>"

    with request_scope() as session:
        assert _compose(Fragment(), session=session).body == "<p>hi</p>"


def test_a_disjoint_nested_region_is_preserved_across_a_parent_swap():
    """The whole path: recorder wired by the walk, keys compared, stamp emitted."""
    with request_scope() as session:
        # A nested root only carries data-pjx-id/-type once stamp_reactive_root_attrs
        # has run. Production wires it per request (pyjinhx/integrations/fastapi.py);
        # a bare session in a test does not, so this test wires it the same way.
        session.on_rendered.append(stamp_reactive_root_attrs)
        registry.register_instance(ShellWidget.__name__, "shell", "resolved-entry")
        add_dirtied(["todos"])
        session.pjx_mounted = [
            {"type": "shell_widget", "id": "shell", "load": None, "hash": "stale"}
        ]
        body = _compose(None, session=session).body
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='shell']\"" in body
    start = body.index('data-pjx-id="side"')
    assert 'hx-preserve="true"' in body[start : body.index(">", start) + 1]


def test_a_nested_region_this_request_dirtied_is_not_preserved():
    """The request's own dirtied keys reach oob_swaps, not an empty default set.

    Sibling of the test above, and the half of the pair that can tell whether
    `_fan_out` actually hands its dirtied keys on: with none of them travelling,
    every nested region looks disjoint and gets held back, including this one,
    which this request dirtied outright.
    """
    with request_scope() as session:
        session.on_rendered.append(stamp_reactive_root_attrs)
        registry.register_instance(ShellWidget.__name__, "shell", "resolved-entry")
        add_dirtied(["todos", "sidebar"])
        session.pjx_mounted = [
            {"type": "shell_widget", "id": "shell", "load": None, "hash": "stale"}
        ]
        body = _compose(None, session=session).body
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='shell']\"" in body
    assert 'data-pjx-id="side"' in body
    assert "hx-preserve" not in body
