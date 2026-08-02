"""Composition tests: ReactiveResponse joins the primary body with OOB fragments."""

import dataclasses
from pathlib import Path
from typing import Annotated

import pytest
from markupsafe import Markup

from pyjinhx2 import discovery, registry
from pyjinhx2.reactive import cache
from pyjinhx2.reactive.cache import cache_get, cache_has, cache_put
from pyjinhx2.reactive.component import PjxKey, ReactiveComponent
from pyjinhx2.reactive.response import ReactiveResponse
from pyjinhx2.session import add_dirtied, request_scope

LOAD_CALLS: list[str | None] = []


class ResponseWidget(ReactiveComponent, react=("todos",)):
    """A reactive component keyed by ``pjx_key``, dirtied by the ``todos`` key."""

    pjx_key: Annotated[str, PjxKey()] = ""

    def load(self) -> str:
        LOAD_CALLS.append(self.pjx_key)
        return f"data:{self.pjx_key}"


_TEMPLATE_DIR = "templates"
"""Set by `_publish_registry` to this test's tmp_path.

`RenderSession(template_dir="templates")` (the class default) does not exist relative to
the test process's cwd, so every test must enter `scope()` rather than bare
`request_scope()` or the dirty path's `render_level()` raises TemplateNotFound instead of
exercising the code under test.
"""


@pytest.fixture(autouse=True)
def _publish_registry(tmp_path, monkeypatch):
    """Publish a tag -> class map for ResponseWidget and point it at a real template."""
    global _TEMPLATE_DIR
    LOAD_CALLS.clear()
    template = tmp_path / "response_widget.pjx"
    template.write_text("<div>{{ pjx_key }}</div>")
    discovery.build_registry(tmp_path, [ResponseWidget])
    # `_resolve_template_path` probes the class's defining module directory, not the
    # dir passed to build_registry; repoint the descriptor at the tmp_path file, using
    # the bare filename because RenderSession's FileSystemLoader joins names under
    # template_dir and would never open an absolute path.
    ResponseWidget.__pjx_descriptor__ = dataclasses.replace(
        ResponseWidget.__pjx_descriptor__, template_path=Path(template.name)
    )
    _TEMPLATE_DIR = str(tmp_path)
    yield


def scope():
    """`request_scope()` bound to this test's tmp_path template dir."""
    return request_scope(_TEMPLATE_DIR)


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


def test_no_dirtied_and_no_mounted_leaves_primary_untouched():
    with scope():
        response = ReactiveResponse(primary=Markup("<p>hello</p>"))
        assert response.body == Markup("<p>hello</p>")
        assert str(response) == "<p>hello</p>"
        assert response.__html__() == Markup("<p>hello</p>")


def test_dirty_mounted_region_appends_an_oob_fragment_after_the_primary():
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        response = ReactiveResponse(
            primary=Markup("<p>hello</p>"), mounted=[entry("a", load="todo-1")]
        )
        body = str(response)
        assert body.startswith("<p>hello</p>")
        assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in body


def test_absent_primary_yields_oob_fragments_only():
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        response = ReactiveResponse(primary=None, mounted=[entry("a", load="todo-1")])
        body = str(response)
        assert body.startswith("<div")
        assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in body


def test_region_already_in_the_primary_is_not_swapped_again():
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        primary = Markup('<div data-pjx-id="a">fresh</div>')
        response = ReactiveResponse(
            primary=primary, mounted=[entry("a", load="todo-1")]
        )
        assert response.body == primary
        assert "hx-swap-oob" not in str(response)


def test_malformed_mounted_header_degrades_to_primary_only():
    with scope():
        add_dirtied(["todos"])
        response = ReactiveResponse(primary=Markup("<p>hello</p>"), mounted="{not json")
        assert response.body == Markup("<p>hello</p>")


def test_raw_json_string_manifest_is_parsed_and_fans_out():
    """The header arrives as a JSON string on the wire, not a pre-parsed list."""
    with scope():
        add_dirtied(["todos"])
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        mounted = '[{"id":"a","type":"response_widget","load":"1","hash":"stale"}]'
        body = str(ReactiveResponse(primary="", mounted=mounted).body)
    assert "outerHTML:[data-pjx-id='a']" in body


@pytest.mark.parametrize("mounted", [None, ""])
def test_absent_manifest_leaves_the_primary_untouched(mounted):
    with scope():
        add_dirtied(["todos"])
        response = ReactiveResponse(primary="<p>x</p>", mounted=mounted)
        assert response.candidates() == []
        assert str(response.body) == "<p>x</p>"


def test_primary_only_response_sets_no_headers():
    with scope():
        response = ReactiveResponse(primary=Markup("<p>hello</p>"))
        assert response.headers == {}


def test_primary_plus_oob_fragments_sets_no_headers():
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        response = ReactiveResponse(
            primary=Markup("<p>hello</p>"), mounted=[entry("a", load="todo-1")]
        )
        assert "hx-swap-oob" in str(response)
        assert response.headers == {}


def test_oob_only_response_sets_reswap_none():
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        response = ReactiveResponse(primary=None, mounted=[entry("a", load="todo-1")])
        assert "hx-swap-oob" in str(response)
        assert response.headers == {"HX-Reswap": "none"}


def test_empty_response_sets_reswap_none():
    with scope():
        response = ReactiveResponse()
        assert str(response) == ""
        assert response.headers == {"HX-Reswap": "none"}


def test_whitespace_only_primary_counts_as_no_primary():
    with scope():
        response = ReactiveResponse(primary=Markup("   \n\t "))
        assert response.headers == {"HX-Reswap": "none"}


def test_reading_headers_does_not_mutate_the_response():
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        response = ReactiveResponse(primary=None, mounted=[entry("a", load="todo-1")])
        primary_before = response.primary
        mounted_before = response.mounted

        assert response.headers == {"HX-Reswap": "none"}

        # `headers` only reads `self.primary` — it must not touch the raw inputs
        # (`candidates()`/`body` re-run the load path and are not idempotent across
        # repeated calls, which is a pre-existing, unrelated engine property).
        assert response.primary is primary_before
        assert response.mounted is mounted_before
        assert "hx-swap-oob" in str(response.body)


def test_redirect_mode_emits_hx_redirect_header():
    """A redirect-mode response asks the browser for a full navigation."""
    response = ReactiveResponse(primary="<div>x</div>", redirect="/login")

    assert response.headers["HX-Redirect"] == "/login"
    assert "HX-Location" not in response.headers


def test_location_mode_emits_hx_location_header():
    """A location-mode response asks htmx for a client-side navigation."""
    response = ReactiveResponse(
        primary="<div>x</div>", redirect="/login", redirect_mode="location"
    )

    assert response.headers["HX-Location"] == "/login"
    assert "HX-Redirect" not in response.headers


def test_headers_without_redirect_are_unchanged():
    """Non-redirect responses keep the HX-Reswap-only behavior."""
    assert ReactiveResponse(primary="<div>x</div>").headers == {}
    assert ReactiveResponse(primary="").headers == {"HX-Reswap": "none"}


def test_redirect_and_reswap_both_appear_on_an_empty_body():
    """The redirect key is added on top of whatever HX-Reswap already decided."""
    response = ReactiveResponse(primary="", redirect="/login")

    assert response.headers == {"HX-Reswap": "none", "HX-Redirect": "/login"}


@pytest.mark.parametrize("mode", ["redirect", "location"])
def test_empty_redirect_url_raises(mode):
    """An empty URL would emit a meaningless header, so it is rejected up front."""
    with pytest.raises(ValueError):
        ReactiveResponse(redirect="", redirect_mode=mode)


def test_redirect_does_not_change_the_body():
    """Redirect state is header-only; body composition is untouched."""
    response = ReactiveResponse(primary="<div>x</div>", redirect="/login")

    assert str(response.body) == "<div>x</div>"


def test_a_dirtied_key_evicts_its_cache_entry_so_the_region_re_renders():
    """A cached load result for a dirtied key must not answer "clean"."""
    with scope():
        cache_put(ResponseWidget, "1", "stale-payload", react_keys=("todos",))
        registry.register_instance(ResponseWidget.__name__, "a", "entry")
        add_dirtied(["todos"])
        [candidate] = ReactiveResponse(
            primary="", mounted=[mounted_entry("a", load="1")]
        ).candidates()
        assert candidate.status == "dirty"
        assert cache_has(ResponseWidget, "1") is True  # re-loaded, not left evicted


def test_an_undirtied_cache_entry_survives_the_fan_out():
    """Eviction is scoped to the dirtied keys; unrelated entries stay cached."""
    with scope():
        cache_put(ResponseWidget, "1", "payload", react_keys=("other",))
        add_dirtied(["todos"])
        ReactiveResponse(primary="", mounted=[]).candidates()
        assert cache_get(ResponseWidget, "1") == "payload"


def test_reading_candidates_twice_reinvalidates_and_reloads_each_time(monkeypatch):
    """Each `candidates()` call re-runs invalidation and reload for dirtied keys."""
    calls: list[set[str]] = []
    original = cache.invalidate
    monkeypatch.setattr(
        cache, "invalidate", lambda keys: (calls.append(set(keys)), original(keys))[1]
    )
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "entry")
        add_dirtied(["todos"])
        response = ReactiveResponse(primary="", mounted=[mounted_entry("a", load="1")])
        response.candidates()
        response.candidates()
    assert all("todos" in seen for seen in calls)
    assert LOAD_CALLS == ["1", "1"]


def test_a_dynamic_dirty_key_evicts_the_instance_it_names():
    """#488's other deferred half: dynamic keys must reach the cache, not just fan-out.

    `@mutates(..., key=...)` / `dirty(reactive_key(KEY, arg))` dirty *only* the
    composite ``"todos:1"`` form (see `mutations.py`) — never the bare static key
    alongside it. Task 5 taught `_matches_dirtied` to read that form; this proves
    the cache's reverse index also understands it, not just the fan-out walk.

    Deviation from the plan's literal test: the plan seeds the cache via a bare
    `cache_put(..., react_keys=("todos",))`, which bypasses `_wrap_load`
    entirely and so can never observe the `_wrap_load` reverse-index fix no
    matter what production code does. Populate the cache through a real
    `.load()` call instead, so the entry is indexed exactly the way
    `_wrap_load` indexes it in production — under both the bare and the
    composite form — which is the one path this test is meant to exercise.
    """
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "entry")
        ResponseWidget(pjx_key="1").load()
        add_dirtied(["todos:1"])
        [candidate] = ReactiveResponse(
            primary="", mounted=[mounted_entry("a", load="1")]
        ).candidates()
        assert candidate.status == "dirty"


def test_candidates_is_empty_without_mounted_or_dirtied():
    """Nothing mounted and nothing dirtied means there is nothing to fan out to."""
    with scope():
        assert ReactiveResponse(primary=Markup("<p>hello</p>")).candidates() == []


def test_candidates_is_empty_when_mounted_but_nothing_dirtied():
    """A mounted region only becomes a candidate once a key it reacts to is dirtied."""
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        response = ReactiveResponse(
            primary=Markup("<p>hello</p>"), mounted=[entry("a", load="todo-1")]
        )
        assert response.candidates() == []


def test_candidates_is_empty_when_dirtied_but_nothing_mounted():
    """A dirtied key with an empty manifest has no region to swap."""
    with scope():
        add_dirtied(["todos"])
        assert ReactiveResponse(primary=Markup("<p>hello</p>")).candidates() == []


def test_two_dirty_regions_each_get_exactly_one_fragment_in_manifest_order():
    """Every dirtied, mounted region is swapped once, in the order the client sent."""
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        registry.register_instance(ResponseWidget.__name__, "b", "resolved-entry")
        add_dirtied(["todos"])
        response = ReactiveResponse(
            primary=Markup("<p>hello</p>"),
            mounted=[entry("a", load="todo-1"), entry("b", load="todo-2")],
        )
        body = str(response)

        first = "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\""
        second = "hx-swap-oob=\"outerHTML:[data-pjx-id='b']\""
        assert body.count(first) == 1
        assert body.count(second) == 1
        assert body.index(first) < body.index(second)
        assert body.index("<p>hello</p>") < body.index(first)


def test_candidates_follows_manifest_order():
    """`candidates()` mirrors manifest order, which is what fixes fragment order."""
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        registry.register_instance(ResponseWidget.__name__, "b", "resolved-entry")
        add_dirtied(["todos"])
        response = ReactiveResponse(
            mounted=[entry("b", load="todo-2"), entry("a", load="todo-1")]
        )
        assert [c.instance_id for c in response.candidates()] == ["b", "a"]


def test_html_returns_markup_and_str_returns_plain_text():
    """`__html__` keeps Markup so templates do not re-escape; `__str__` is plain.

    Uses a primary-only response (no mounted/dirtied) because `body` re-walks the
    manifest on every access and `get_dirtied()` is consumed on read — a mounted
    response would render different content on each of the two calls below.
    """
    with scope():
        response = ReactiveResponse(primary=Markup("<p>hello</p>"))
        rendered = response.__html__()

        assert isinstance(rendered, Markup)
        assert type(str(response)) is str
        assert str(rendered) == str(response)


def test_html_is_not_escaped_when_interpolated_into_markup():
    """The whole point of `__html__`: Markup.format leaves the body as live HTML."""
    with scope():
        response = ReactiveResponse(primary=Markup("<p>hello</p>"))
        assert Markup("<main>{}</main>").format(response) == Markup(
            "<main><p>hello</p></main>"
        )


def test_unknown_redirect_mode_falls_through_to_hx_location():
    """`redirect_mode` is not validated at runtime; only "redirect" selects HX-Redirect.

    Documents current behavior — the Literal type is the contract, and anything the
    type checker would have rejected takes the else branch rather than raising.
    """
    response = ReactiveResponse(
        primary="<div>x</div>",
        redirect="/login",
        redirect_mode="bogus",  # pyright: ignore[reportArgumentType]
    )

    assert response.headers["HX-Location"] == "/login"
    assert "HX-Redirect" not in response.headers


def test_construction_touches_nothing_outside_a_request_scope():
    """Constructing is inert: no session read, no manifest parse, no render."""
    response = ReactiveResponse(
        primary=Markup("<p>hello</p>"), mounted=[entry("a", load="todo-1")]
    )

    # Inputs are stored verbatim — not parsed, not normalized, not walked.
    assert response.primary == Markup("<p>hello</p>")
    assert response.mounted == [entry("a", load="todo-1")]


def test_candidates_outside_a_request_scope_returns_empty():
    """The session lookup degrades to empty rather than raising with no scope entered."""
    response = ReactiveResponse(
        primary=Markup("<p>hello</p>"), mounted=[entry("a", load="todo-1")]
    )
    assert response.candidates() == []


def test_none_and_empty_string_primary_compose_the_same_empty_body():
    """`Markup(self.primary or "")` collapses both falsy inputs to an empty body."""
    with scope():
        assert ReactiveResponse(primary=None).body == Markup("")
        assert ReactiveResponse(primary="").body == Markup("")
        assert str(ReactiveResponse(primary=None)) == ""
        assert str(ReactiveResponse(primary="")) == ""


def test_plain_string_and_markup_primary_compose_identically():
    """`Markup()` adopts a plain str as-is (no escaping); handlers must escape upstream."""
    with scope():
        assert ReactiveResponse(primary="<p>hi</p>").body == Markup("<p>hi</p>")
        assert ReactiveResponse(primary=Markup("<p>hi</p>")).body == Markup("<p>hi</p>")


def test_primary_with_dunder_html_is_used_as_markup():
    """An object exposing `__html__` is adopted by `Markup()` without escaping."""

    class Fragment:
        def __html__(self) -> str:
            return "<p>hi</p>"

    with scope():
        assert str(ReactiveResponse(primary=Fragment()).body) == "<p>hi</p>"


def test_redirect_headers_survive_a_malformed_mounted_header():
    """Manifest degradation is body-side; it must not drop the redirect header."""
    with scope():
        add_dirtied(["todos"])
        response = ReactiveResponse(
            primary=Markup("<p>hello</p>"), mounted="{not json", redirect="/login"
        )

        assert response.body == Markup("<p>hello</p>")
        assert response.headers == {"HX-Redirect": "/login"}


def test_malformed_mounted_with_empty_primary_still_sets_both_headers():
    """The degraded body is empty, so HX-Reswap and the redirect both apply."""
    with scope():
        add_dirtied(["todos"])
        response = ReactiveResponse(
            primary=None,
            mounted="{not json",
            redirect="/login",
            redirect_mode="location",
        )

        assert str(response.body) == ""
        assert response.headers == {"HX-Reswap": "none", "HX-Location": "/login"}
