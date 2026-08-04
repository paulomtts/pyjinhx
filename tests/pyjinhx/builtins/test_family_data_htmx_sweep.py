"""Data + HTMX-heavy builtins exercised together in one request.

Each individual component is unit-tested by its own module; this file only
asserts the cross-cutting properties that per-component tests cannot see:
fan-out fan set, cache-hit resolution of untouched regions, nesting dedup,
loading-overlay markup inside reactive flows, and request-scope isolation.

The builtins are plain BaseComponents, so the reactive regions are declared
here: three wrappers whose templates mount the builtins and whose ``react``
keys the scenarios dirty.
"""

import dataclasses
import re
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import Field

from pyjinhx import discovery, registry
from pyjinhx._component import Slot, _pascal_to_snake
from pyjinhx.builtins.pjx_lazy_load import PJXLazyLoad
from pyjinhx.builtins.pjx_page_loader import PJXPageLoader
from pyjinhx.builtins.pjx_paginator import PJXPaginator
from pyjinhx.builtins.pjx_region_loader import PJXRegionLoader
from pyjinhx.builtins.pjx_table import PJXTable
from pyjinhx.builtins.pjx_table_body import PJXTableBody
from pyjinhx.builtins.pjx_table_cell import PJXTableCell
from pyjinhx.builtins.pjx_table_head import PJXTableHead
from pyjinhx.builtins.pjx_table_header_cell import PJXTableHeaderCell
from pyjinhx.builtins.pjx_table_row import PJXTableRow
from pyjinhx.reactive.cache import cache_has, invalidate
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.reactive.fanout import walk_manifest
from pyjinhx.reactive.root_attrs import stamp_reactive_root_attrs
from pyjinhx.rendering import render
from pyjinhx.responses import PjxResponse, compose
from pyjinhx.session import (
    RenderSession,
    add_dirtied,
    get_dirtied,
    get_instances,
    request_scope,
)

PAGE = "page"
ROWS = "rows"

STORE = {"page": 1, "rows": ["a", "b"]}
"""App state the regions' load() reads, standing in for a database."""

LOAD_CALLS: list[str] = []
"""One entry per uncached load() body run, for cache-hit assertions."""


class TableRegion(ReactiveComponent, react=(ROWS,)):
    """A table wrapped in a region loader; dirtied by the ``rows`` key.

    ``load()`` writes ``rows`` and ``table`` as side effects rather than
    returning them: the engine binds no special "load result" variable into
    the template context (checked against render.py/render_context.py — a
    ReactiveComponent's own fields are what the template sees), so the data
    has to land on plain fields for the template to read.

    ``table`` is built here, in Python, as a real ``PJXTable`` instance rather
    than composed from PascalCase tags nested inside ``table_region.pjx``.
    Reproduced directly against this branch: a Slot field's *string* value —
    which is what a tag-nested child's inner markup becomes (``ref.inner`` in
    ``render.py``'s ``_instantiate_child``) — is not Markup-exempted from
    autoescape anywhere in the L0/L1 pipeline yet (render_context.py's
    ``build_context`` only wraps *component-valued* Slot fields; a plain
    string Slot field passes through untouched and Jinja's ``{{ content }}``
    escapes it). ``tests/pyjinhx/test_render_context.py`` names this
    directly: "String-valued Slot fields pass as-is (will be wrapped in
    Markup by L1)" — a documented, deferred gap, not something #531 owns.
    Composing ``table`` as a live component tree instead uses the officially
    working path (ComponentNode + the Jinja finalize/splice machinery,
    exactly what ``tests/pyjinhx/test_direct_nesting.py`` covers) and avoids
    it entirely. The corollary is that ``content`` on ``PJXTable``/
    ``PJXTableBody`` holds exactly one value each — multiple sibling rows
    are out of reach for either composition route today — so this harness
    nests one row deep (Table -> Body -> Row -> Cell) instead of the
    Head+Body multi-row shape #531's spec sketches; see the PR body.
    """

    pjx_key: Annotated[str, PjxKey()] = "main"
    rows: list[str] = Field(default_factory=list)
    table: Slot = ""

    @classmethod
    def load(cls, pjx_key: str) -> "TableRegion":
        LOAD_CALLS.append(f"table:{pjx_key}")
        rows = list(STORE["rows"])
        instance = cls(pjx_key=pjx_key, rows=rows)
        # Nested ids are keyed off pjx_key, not instance.id: this instance is a
        # throwaway _load_reactive_child/_mount_root copy fields out of (see
        # #726), so its own auto-generated id is not the mounted region's
        # final id and, worse, keeps incrementing across request scopes -
        # deriving from it would make these nested ids leak that global
        # counter instead of staying a pure function of which key was loaded.
        instance.table = PJXTable(
            id=f"tbl-{pjx_key}",
            content=PJXTableBody(
                id=f"tbody-{pjx_key}",
                content=PJXTableRow(
                    id=f"row-{pjx_key}",
                    content=PJXTableCell(id=f"cell-{pjx_key}", content=", ".join(rows)),
                ),
            ),
        )
        return instance


class PaginatorRegion(ReactiveComponent, react=(PAGE,)):
    """The paginator beneath the table; dirtied by the ``page`` key."""

    pjx_key: Annotated[str, PjxKey()] = "main"
    page: int = 1

    @classmethod
    def load(cls, pjx_key: str) -> "PaginatorRegion":
        LOAD_CALLS.append(f"paginator:{pjx_key}")
        return cls(pjx_key=pjx_key, page=int(STORE["page"]))


class PageShell(ReactiveComponent, react=(PAGE,)):
    """The page-level region: a PageLoader overlay wrapping the table region."""

    pjx_key: Annotated[str, PjxKey()] = "shell"

    @classmethod
    def load(cls, pjx_key: str) -> "PageShell":
        LOAD_CALLS.append("shell")
        return cls(pjx_key=pjx_key)


class BoomRegion(ReactiveComponent, react=(ROWS,)):
    """A region whose load() raises, to prove failures stay local."""

    @classmethod
    def load(cls) -> "BoomRegion":
        raise RuntimeError("boom")


TEMPLATES = {
    "table_region.pjx": (
        '<div id="{{ id }}" class="region">'
        '<PJXRegionLoader id="rl-{{ id }}"/>'
        "{{ table }}"
        '<PJXLazyLoad id="sentinel-{{ id }}" url="/rows?after={{ rows|length }}" tag="div"/>'
        "</div>"
    ),
    "paginator_region.pjx": (
        '<div id="{{ id }}" class="region">'
        '<PJXPaginator id="pg-{{ id }}" url="/rows?page={page}" page="{{ page }}" total_pages="5"/>'
        "</div>"
    ),
    "page_shell.pjx": (
        '<div id="{{ id }}" class="shell">'
        '<PJXPageLoader id="pl-{{ id }}"/>'
        '<TableRegion id="t-main" pjx_key="main"/>'
        '<PaginatorRegion id="p-main" pjx_key="main"/>'
        "</div>"
    ),
    "boom_region.pjx": '<div id="{{ id }}">boom</div>',
}


@pytest.fixture(autouse=True)
def family(tmp_path: Path):
    """Publish the tag map, write wrapper templates, reset per-test app state."""
    LOAD_CALLS.clear()
    STORE.update(page=1, rows=["a", "b"])
    classes = [
        TableRegion,
        PaginatorRegion,
        PageShell,
        BoomRegion,
        PJXTable,
        PJXTableHead,
        PJXTableBody,
        PJXTableRow,
        PJXTableCell,
        PJXTableHeaderCell,
        PJXPaginator,
        PJXLazyLoad,
        PJXRegionLoader,
        PJXPageLoader,
    ]
    # `build_registry(dir, classes)` only claims a tag for a class if a file
    # named `<tag>.pjx` exists *somewhere under `dir`* (`walk_templates` does
    # an `rglob("*.pjx")` and matches by stem only — content is never read,
    # and a class's own `template_path` is resolved separately). The builtins'
    # real `.pjx` files live under `pyjinhx/builtins/**`, not under `tmp_path`,
    # so registering only the wrapper templates here leaves every `PJX*` tag
    # unclaimed and `_fill_children` silently falls back to passthrough markup.
    # Write the wrapper templates first (their content matters), then touch
    # empty placeholder files for every builtin tag this sweep composes (only
    # the stem matters), and only then build the registry once.
    for name, body in TEMPLATES.items():
        (tmp_path / name).write_text(body)
    for cls in (
        PJXTable,
        PJXTableHead,
        PJXTableBody,
        PJXTableRow,
        PJXTableCell,
        PJXTableHeaderCell,
        PJXPaginator,
        PJXLazyLoad,
        PJXRegionLoader,
        PJXPageLoader,
    ):
        placeholder = tmp_path / f"{_pascal_to_snake(cls.__name__)}.pjx"
        if not placeholder.exists():
            placeholder.write_text("")
    discovery.build_registry(tmp_path, classes)
    for cls, name in (
        (TableRegion, "table_region.pjx"),
        (PaginatorRegion, "paginator_region.pjx"),
        (PageShell, "page_shell.pjx"),
        (BoomRegion, "boom_region.pjx"),
    ):
        # `_resolve_template_path` probes the class's defining module dir (this
        # test file's), so each wrapper descriptor is repointed at the tmp_path
        # file. Absolute, because the sweep renders with template_dir="/" — the
        # same search root the sibling builtin tests use so the builtins' own
        # absolute template paths keep resolving.
        cls.__pjx_descriptor__ = dataclasses.replace(
            cls.__pjx_descriptor__, template_path=tmp_path / name
        )
    yield


def scope():
    """A request scope whose session stamps reactive root attrs and registers instances."""
    session = RenderSession()
    session.on_rendered.append(stamp_reactive_root_attrs)
    session.on_rendered.append(registry.register_rendered_instance)
    return request_scope(session=session)


def entry(type_name: str, instance_id: str, load: object, hash_: str = "stale") -> dict:
    """One synthetic X-PJX-Mounted entry."""
    return {"type": type_name, "id": instance_id, "load": load, "hash": hash_}


_HASH_RE_TEMPLATE = r'data-pjx-id="{}"[^>]*data-pjx-hash="([^"]+)"'


def _hash_of(html: str, instance_id: str) -> str:
    """The ``data-pjx-hash`` stamped next to a given ``data-pjx-id``."""
    match = re.search(_HASH_RE_TEMPLATE.format(re.escape(instance_id)), html)
    assert match is not None, f"no data-pjx-hash found next to id {instance_id!r}"
    return match.group(1)


def compose_body(
    primary: str, mounted: list[dict[str, object]], session: RenderSession
) -> str:
    """The fan-out body compose() builds for ``primary`` against ``mounted``.

    compose() reads the client's manifest off the session rather than taking it
    as an argument, so the manifest is parked there first.
    """
    session.pjx_mounted = mounted
    composed = compose(primary, session=session)
    assert isinstance(composed, PjxResponse)
    return composed.body


def test_full_family_combo_renders_single_pass_no_error():
    with scope() as session:
        html = render(PageShell(id="shell"), session)

    # The spinner divs share the loader classes' string prefix (e.g.
    # ``pjx-page-loader__spinner``), so the root's markers must be matched
    # exactly, not by substring, to avoid double-counting them.
    assert html.count("data-pjx-page-loader") == 1
    assert html.count('class="pjx-region-loader"') == 1
    assert html.count("<table ") == 1
    assert html.count("data-pjx-lazy-load") == 1
    assert html.count('class="pjx-paginator"') == 1
    # ADR 0001: reactive regions are stamped for outerHTML-only OOB swaps.
    assert 'data-pjx-id="shell"' in html
    assert 'data-pjx-id="t-main"' in html
    assert 'data-pjx-id="p-main"' in html


def test_paginator_mutation_swaps_only_the_page_keyed_regions():
    with scope() as session:
        render(PageShell(id="shell"), session)
        mounted = [
            entry("page_shell", "shell", "shell"),
            entry("table_region", "t-main", "main"),
            entry("paginator_region", "p-main", "main"),
        ]
        candidates = walk_manifest(mounted, {PAGE}, session=session)

    swapped = {c.instance_id for c in candidates}
    # "shell" reacts to PAGE, so it resolves "dirty" here regardless of its
    # own cache state, and its fresh re-render recurses into PaginatorRegion —
    # "p-main" ends up nested inside "shell"'s own freshly-built tree and
    # _drop_nested drops it as a redundant swap, exactly like a
    # primary-response exclusion.
    assert swapped == {"shell"}
    assert "t-main" not in swapped
    assert "p-main" not in swapped


def test_untouched_region_is_a_cache_hit_not_a_recompute():
    with scope() as session:
        render(PageShell(id="shell"), session)
        assert "table:main" in LOAD_CALLS
        before = list(LOAD_CALLS)

        walk_manifest(
            [entry("table_region", "t-main", "main")],
            {PAGE},
            session=session,
        )

        assert LOAD_CALLS == before
        assert cache_has(TableRegion, "main")
        assert registry.resolve("TableRegion", "t-main") is not None


def test_identical_content_is_hash_gated_out_of_the_swap():
    with scope() as session:
        html = render(PageShell(id="shell"), session)
        current = _hash_of(html, "p-main")
        # The real Load path (compose()'s fan-out) always calls invalidate()
        # before walk_manifest(): otherwise the still-cached entry answers
        # "clean" and the hash gate never runs at all.
        invalidate({PAGE})
        candidates = walk_manifest(
            [entry("paginator_region", "p-main", "main", hash_=current)],
            {PAGE},
            session=session,
        )

    assert [c.instance_id for c in candidates] == []


def test_table_region_in_primary_is_not_also_swapped_oob():
    with scope() as session:
        primary = render(TableRegion(id="t-main", pjx_key="main"), session)
        invalidate({ROWS})
        candidates = walk_manifest(
            [entry("table_region", "t-main", "main")],
            {ROWS},
            session=session,
            primary_html=primary,
        )

    assert [c.instance_id for c in candidates] == []
    # The lazyload sentinel is nested inside the region already excluded by
    # primary_html — one region, one appearance, not a second copy from a
    # would-be independent sentinel swap.
    assert primary.count("data-pjx-lazy-load") == 1


def test_dropping_primary_html_makes_the_excluded_region_swap_again():
    """RED proof: without primary_html threaded through, the exclusion above
    does not fire and the region reappears as a candidate."""
    with scope() as session:
        primary = render(TableRegion(id="t-main", pjx_key="main"), session)
        invalidate({ROWS})
        candidates = walk_manifest(
            [entry("table_region", "t-main", "main")],
            {ROWS},
            session=session,
        )

    assert [c.instance_id for c in candidates] == ["t-main"]
    assert primary  # only read to avoid an unused-variable lint complaint


def test_table_inside_pageloader_shell_is_not_double_swapped():
    with scope() as session:
        primary = render(PageShell(id="shell"), session)
        # compose() reads this request's dirtied set off the ContextVar
        # (get_dirtied()), not a parameter, and calls invalidate() itself —
        # add_dirtied() is the one call this needs.
        add_dirtied({ROWS})
        body = compose_body(
            primary,
            [
                entry("page_shell", "shell", "shell"),
                entry("table_region", "t-main", "main"),
            ],
            session,
        )

    assert str(body).count('data-pjx-id="t-main"') == 1


def test_region_loader_overlay_rides_along_with_a_dirty_table_swap():
    STORE["rows"] = ["a", "b", "c"]
    with scope() as session:
        render(PageShell(id="shell"), session)
        add_dirtied({ROWS})
        body = compose_body("", [entry("table_region", "t-main", "main")], session)

    assert 'class="pjx-region-loader"' in body
    assert 'role="status"' in body
    assert 'aria-live="polite"' in body
    assert body.count('class="pjx-region-loader__spinner"') == 1


def test_page_loader_overlay_survives_a_page_level_swap():
    with scope() as session:
        render(PageShell(id="shell"), session)
        add_dirtied({PAGE})
        body = compose_body("", [entry("page_shell", "shell", "shell")], session)

    assert "data-pjx-page-loader" in body
    assert 'data-nav-targets="app-content"' in body
    assert body.count('class="pjx-page-loader__spinner"') == 1


def test_overlay_markup_is_not_duplicated_across_sibling_regions():
    STORE["rows"] = ["a", "b", "c"]
    STORE["page"] = 2
    with scope() as session:
        render(PageShell(id="shell"), session)
        add_dirtied({ROWS, PAGE})
        body = compose_body(
            "",
            [
                entry("table_region", "t-main", "main"),
                entry("paginator_region", "p-main", "main"),
            ],
            session,
        )

    # Only the table region carries a region-loader overlay; the paginator
    # region carries none, so one dirty swap of each must not multiply or
    # cross-contaminate the other's markup.
    assert body.count("pjx-region-loader__spinner") == 1
    assert body.count("pjx-page-loader") == 0


def test_request_scopes_do_not_share_registry_cache_or_dirtied_state():
    with scope() as first:
        render(PageShell(id="shell"), first)
        assert cache_has(TableRegion, "main")
        first_ids = set(get_instances())

    with scope() as second:
        assert not cache_has(TableRegion, "main")
        assert get_instances() == {}
        assert get_dirtied() == set()
        render(PageShell(id="shell"), second)
        assert set(get_instances()) == first_ids


def test_a_nested_scope_hands_state_back_to_the_outer_scope():
    with scope() as outer:
        render(TableRegion(id="t-main", pjx_key="main"), outer)
        add_dirtied({ROWS})
        with scope() as inner:
            assert get_dirtied() == set()
            render(PaginatorRegion(id="p-main", pjx_key="main"), inner)
        assert get_dirtied() == {ROWS}
        assert registry.resolve("TableRegion", "t-main") is not None


def test_a_failing_region_does_not_corrupt_its_siblings():
    with scope() as session:
        render(PageShell(id="shell"), session)
        # BoomRegion.load() is called directly here, not through render():
        # render() would call load() too (it now mounts a reactive root the
        # same way a ChildRef-discovered child is mounted), but this test
        # wants the raised RuntimeError itself, not an HTTP-shaped failure
        # from deeper in the render pipeline.
        with pytest.raises(RuntimeError):
            BoomRegion(id="boom").load()

        assert registry.resolve("TableRegion", "t-main") is not None
        assert cache_has(TableRegion, "main")
        invalidate({ROWS})
        candidates = walk_manifest(
            [entry("table_region", "t-main", "main")], {ROWS}, session=session
        )
        assert [c.instance_id for c in candidates] == ["t-main"]
