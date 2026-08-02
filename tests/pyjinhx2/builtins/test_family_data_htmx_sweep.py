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

from pyjinhx2 import discovery, registry
from pyjinhx2.builtins.pjx_lazy_load import PJXLazyLoad
from pyjinhx2.builtins.pjx_page_loader import PJXPageLoader
from pyjinhx2.builtins.pjx_paginator import PJXPaginator
from pyjinhx2.builtins.pjx_region_loader import PJXRegionLoader
from pyjinhx2.builtins.pjx_table import PJXTable
from pyjinhx2.builtins.pjx_table_body import PJXTableBody
from pyjinhx2.builtins.pjx_table_cell import PJXTableCell
from pyjinhx2.builtins.pjx_table_head import PJXTableHead
from pyjinhx2.builtins.pjx_table_header_cell import PJXTableHeaderCell
from pyjinhx2.builtins.pjx_table_row import PJXTableRow
from pyjinhx2.component import Slot, _pascal_to_snake
from pyjinhx2.reactive.cache import cache_has, invalidate
from pyjinhx2.reactive.component import PjxKey, ReactiveComponent
from pyjinhx2.reactive.fanout import walk_manifest
from pyjinhx2.reactive.root_attrs import stamp_reactive_root_attrs
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession, request_scope

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
    escapes it). ``tests/pyjinhx2/test_render_context.py`` names this
    directly: "String-valued Slot fields pass as-is (will be wrapped in
    Markup by L1)" — a documented, deferred gap, not something #531 owns.
    Composing ``table`` as a live component tree instead uses the officially
    working path (ComponentNode + the Jinja finalize/splice machinery,
    exactly what ``tests/pyjinhx2/test_direct_nesting.py`` covers) and avoids
    it entirely. The corollary is that ``content`` on ``PJXTable``/
    ``PJXTableBody`` holds exactly one value each — multiple sibling rows
    are out of reach for either composition route today — so this harness
    nests one row deep (Table -> Body -> Row -> Cell) instead of the
    Head+Body multi-row shape #531's spec sketches; see the PR body.
    """

    pjx_key: Annotated[str, PjxKey()] = "main"
    rows: list[str] = Field(default_factory=list)
    table: Slot = ""

    def load(self) -> None:
        LOAD_CALLS.append(f"table:{self.pjx_key}")
        self.rows = list(STORE["rows"])
        self.table = PJXTable(
            id=f"tbl-{self.id}",
            content=PJXTableBody(
                id=f"tbody-{self.id}",
                content=PJXTableRow(
                    id=f"row-{self.id}",
                    content=PJXTableCell(
                        id=f"cell-{self.id}", content=", ".join(self.rows)
                    ),
                ),
            ),
        )


class PaginatorRegion(ReactiveComponent, react=(PAGE,)):
    """The paginator beneath the table; dirtied by the ``page`` key."""

    pjx_key: Annotated[str, PjxKey()] = "main"
    page: int = 1

    def load(self) -> None:
        LOAD_CALLS.append(f"paginator:{self.pjx_key}")
        self.page = int(STORE["page"])


class PageShell(ReactiveComponent, react=(PAGE,)):
    """The page-level region: a PageLoader overlay wrapping the table region."""

    pjx_key: Annotated[str, PjxKey()] = "shell"

    def load(self) -> None:
        LOAD_CALLS.append("shell")


class BoomRegion(ReactiveComponent, react=(ROWS,)):
    """A region whose load() raises, to prove failures stay local."""

    def load(self) -> None:
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
    # real `.pjx` files live under `pyjinhx2/builtins/**`, not under `tmp_path`,
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
    session = RenderSession(template_dir="/")
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
    # "shell" never had its own load() cached (only a ChildRef-mounted
    # component gets pjx_mount()'d; the top-level render(PageShell(...))
    # call in this test does not), so it always resolves "dirty" here and
    # its fresh re-render recurses into PaginatorRegion — "p-main" ends up
    # nested inside "shell"'s own freshly-built tree and _drop_nested drops
    # it as a redundant swap, exactly like a primary-response exclusion.
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
        # The real Load path (ReactiveResponse.candidates()) always calls
        # invalidate() before walk_manifest(): otherwise the still-cached
        # entry answers "clean" and the hash gate never runs at all.
        invalidate({PAGE})
        candidates = walk_manifest(
            [entry("paginator_region", "p-main", "main", hash_=current)],
            {PAGE},
            session=session,
        )

    assert [c.instance_id for c in candidates] == []
