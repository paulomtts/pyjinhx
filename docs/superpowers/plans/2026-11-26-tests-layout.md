# Tests layout reorganisation: implementation plan

Planning only. Nothing under `tests/` has been moved yet. Every number below was
measured on `refactor/tests-layout` at `ed7e97b5` (master, 1.17.0).

Baseline to preserve:

- `uv run pytest --co -q | tail -1` -> `6296 tests collected`
- `uv run pytest -q | tail -1` -> `6291 passed, 1 skipped, 3 xfailed, 1 xpassed` (about 5m20s, of which 4m30s is browser tests)

## 0. Before starting

Two other branches merge first, and both touch files this plan moves:

- `refactor/flatten-builtins` turns `pyjinhx/builtins/ui/<name>/` into `pyjinhx/builtins/<name>/`.
  `tests/unit/builtins/` below is already flat, so it mirrors that layout. Wherever a table
  here shows `/ "builtins" / "ui"` or `pyjinhx.builtins.ui.`, read it as already rewritten
  by that branch; this plan changes only the `parents[N]` index in front of it.
- `refactor/examples-sfc` rewrites `examples/todo` and may edit the tests under
  `tests/examples/` and `tests/minimal/`. Those two folders are moved here as whole
  folders with globs (steps 4.1 and 4.2), never file by file from a list, so whatever
  that branch leaves in them moves intact.

So: rebase onto master once both are in, then re-record the two baseline lines above.
If the collected count is no longer 6296, use the new number everywhere this plan says
6296. Line numbers in sections 3 and 4.3 are a snapshot of `ed7e97b5` and may be off by
a few lines after the rebase; every step is checked by a grep or a test run, not by a
line number.

Also record the test names, to compare at the end without depending on paths:

```
uv run pytest --co -q | grep :: | sed 's/^[^:]*:://' | sort > /tmp/names.before
```

Hard rules for the implementer: never `git stash`, never `git reset --hard`, do not
push. One commit per numbered step. Run `ruff format .` and `ruff check .` before each
commit (`ruff check` reports a merged file's duplicate definitions as F811 and stray
mid-file imports as E402, which is exactly what a bad merge looks like).

## 1. Final tree

```
tests/
  conftest.py              autouse state resets, write, render_session, session, folder markers
  unit/                    one file per source module, mirroring pyjinhx/      4734 tests
    test_<module>.py         app_context config context descriptor dev importer manifest markers
                             props_header registry render_context responses root_attrs stubgen
                             template_blocks
    assets/ classless/ component/ discovery/ render_cache/ rendering/ segments/ session/ sfc/
                             modules whose tests exceed ~800 lines: one folder, existing files
    slots/                   the one feature folder (slots span markers, render_context, rendering)
    reactive/                test_<module>.py, plus cache/ and component/ folders
    integrations/            test_base.py test_diskcache.py test_setup_dispatch.py fastapi/
    client/                  test_client.py test_inject.py (the Python side of pyjinhx/client)
    builtins/                test_pjx_<name>.py per builtin, test_builtins.py,
                             families/ theme_tokens/ pjx_graph/ pjx_roster_picker/ pjx_select/
  browser/                 everything that needs a Playwright page               971 tests
    conftest.py              chromium guard, page_errors, console_errors
    client/                  pjx.js in chromium (conftest.py: pjx_page, pjx_full_page)
    builtins/                test_pjx_<name>.py, plus pjx_graph/ pjx_roster_picker/ pjx_select/
                             pjx_popover/ pjx_tooltip/
    test_gallery_theme_toggle.py
  docs/                    doc-lint and the docs demo registry                   103 tests
  scripts/                 test_bench.py test_fold_components.py                 109 tests
  packaging/               test_package_layout.py test_minimal_install.py
                           test_import_graph.py                                  250 tests
  apps/                    todo/ (examples/todo) and fewer_files/ (the parity app) 129 tests
  fixtures/
    __init__.py
    templates/<topic>/       basic cycle fastapi integration nesting reactive slots splice discovery
    block_grammar/           unchanged
    fewer_files/             unchanged, so every `tests.fixtures.fewer_files...` name still resolves
    bench/                   bench_builtin_heavy.py and its two .pjx templates
    header_names.py header_import_probe.py
```

| Folder | Test files | Tests collected | Marker |
|---|---|---|---|
| `tests/unit/` | 176 | 4734 | none |
| `tests/browser/` | 77 | 971 | `browser` |
| `tests/docs/` | 9 | 103 | `docs` |
| `tests/scripts/` | 2 | 109 | `slow` |
| `tests/packaging/` | 3 | 250 | `slow` |
| `tests/apps/` | 8 | 129 | `slow` |
| total | 275 | 6296 | |

There is no `fixtures/ui/`. The approved tree lists one, but nothing tracked would go in
it: `tests/ui/` in the main checkout holds only stale `__pycache__` folders left behind
when the old engine was removed (#660), and git ignores them. Delete that folder by hand.

### How the rules were applied

- A source module whose tests total 800 lines or fewer gets one file, `unit/test_<module>.py`,
  built by merging (section 2.2).
- A source module whose tests total more gets `unit/<module>/` holding the files that
  exist today, renamed to drop the repeated prefix and any `_v2`, `_matrix` or `_sweep`
  suffix. Files inside such a folder are not merged with each other: no rule asks for
  it, and every merge risks the isolation problems in section 7.
- A test goes in `browser/` exactly when pytest resolves the `page` or `browser`
  fixture for it. That was read from a real collection, not guessed from file names:
  971 tests, in 77 files after the split. Fourteen files mix both kinds and are split
  (section 4.3).
- In `browser/builtins/`, files belonging to one builtin stay separate files in a
  folder when they define the same harness names (`PAGE`, `STYLE`, `_load`,
  `CONTROLLER`) with different contents. That is the case for popover and select, so
  they get folders even though popover totals only 643 lines.
- The graph and roster picker families keep a folder in `unit/builtins/` although each
  member is its own source module, because each family shares a `parse_html` fixture
  and the two families' versions behave differently (section 4.2).

### Files already over 800 lines

These twelve are single files today and move as they are. Splitting them means
deciding where shared helpers and autouse fixtures go, which is not mechanical, so it
is left out of this refactor (question 1 in section 8).

| File after the move | Lines |
|---|---|
| `browser/builtins/pjx_graph/test_reconcile.py` | 1599 |
| `browser/builtins/pjx_roster_picker/test_pick_remove.py` | 1131 |
| `browser/builtins/pjx_roster_picker/test_swaps.py` | 831 |
| `packaging/test_import_graph.py` | 1114 |
| `scripts/test_fold_components.py` | 1234 |
| `unit/component/test_class_descriptor.py` | 2020 |
| `unit/integrations/fastapi/test_wiring.py` | 954 |
| `unit/reactive/component/test_load_wrap.py` | 808 |
| `unit/reactive/test_fanout.py` | 2659 |
| `unit/segments/test_segments.py` | 1279 |
| `unit/session/test_session.py` | 957 |
| `unit/test_manifest.py` | 1119 |

## 2. Mapping

Paths are relative to `tests/`. "merge k/n" means the file is the k-th of n sources
appended, in that order, into the new file.

### 2.1 Test files

| Old path (under `tests/`) | New path (under `tests/`) | Note |
|---|---|---|
| `examples/test_todo_app.py` | `apps/todo/test_app.py` |  |
| `examples/test_todo_components.py` | `apps/todo/test_components.py` |  |
| `examples/test_todo_context.py` | `apps/todo/test_context.py` |  |
| `examples/test_todo_keys.py` | `apps/todo/test_keys.py` |  |
| `examples/test_todo_store.py` | `apps/todo/test_store.py` |  |
| `examples/test_todo_templates.py` | `apps/todo/test_templates.py` |  |
| `minimal/test_bare_install.py` | `packaging/test_minimal_install.py` |  |
| `pyjinhx/builtins/pjx_accordion/test_pjx_accordion.py` | `unit/builtins/test_pjx_accordion.py` |  |
| `pyjinhx/builtins/pjx_accordion_content/test_pjx_accordion_content.py` | `unit/builtins/test_pjx_accordion_content.py` |  |
| `pyjinhx/builtins/pjx_accordion_group/test_pjx_accordion_group.py` | `unit/builtins/test_pjx_accordion_group.py` |  |
| `pyjinhx/builtins/pjx_accordion_trigger/test_pjx_accordion_trigger.py` | `unit/builtins/test_pjx_accordion_trigger.py` |  |
| `pyjinhx/builtins/pjx_alert/test_pjx_alert.py` | `unit/builtins/test_pjx_alert.py` |  |
| `pyjinhx/builtins/pjx_avatar/test_pjx_avatar.py` | `unit/builtins/test_pjx_avatar.py` |  |
| `pyjinhx/builtins/pjx_avatar_stack/test_pjx_avatar_stack.py` | `unit/builtins/test_pjx_avatar_stack.py` |  |
| `pyjinhx/builtins/pjx_badge/test_pjx_badge.py` | `unit/builtins/test_pjx_badge.py` |  |
| `pyjinhx/builtins/pjx_breadcrumb/test_pjx_breadcrumb.py` | `unit/builtins/test_pjx_breadcrumb.py` |  |
| `pyjinhx/builtins/pjx_button/test_pjx_button.py` | `unit/builtins/test_pjx_button.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_button/test_pjx_button.py` | `browser/builtins/test_pjx_button.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_card/test_pjx_card.py` | `unit/builtins/test_pjx_card.py` |  |
| `pyjinhx/builtins/pjx_card_body/test_pjx_card_body.py` | `unit/builtins/test_pjx_card_body.py` |  |
| `pyjinhx/builtins/pjx_card_footer/test_pjx_card_footer.py` | `unit/builtins/test_pjx_card_footer.py` |  |
| `pyjinhx/builtins/pjx_card_header/test_pjx_card_header.py` | `unit/builtins/test_pjx_card_header.py` |  |
| `pyjinhx/builtins/pjx_carousel/test_pjx_carousel.py` | `unit/builtins/test_pjx_carousel.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_carousel/test_pjx_carousel.py` | `browser/builtins/test_pjx_carousel.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_carousel_slide/test_pjx_carousel_slide.py` | `unit/builtins/test_pjx_carousel_slide.py` |  |
| `pyjinhx/builtins/pjx_chart/test_pjx_chart.py` | `unit/builtins/test_pjx_chart.py` | merge 1/2 |
| `pyjinhx/builtins/pjx_chart/test_pjx_chart_browser.py` | `browser/builtins/test_pjx_chart.py` |  |
| `pyjinhx/builtins/pjx_chart/test_pjx_chart_scale.py` | `unit/builtins/test_pjx_chart.py` | merge 2/2 |
| `pyjinhx/builtins/pjx_chip_input/test_pjx_chip_input.py` | `unit/builtins/test_pjx_chip_input.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_chip_input/test_pjx_chip_input.py` | `browser/builtins/test_pjx_chip_input.py` | split: browser tests (4.3); merge 1/2 |
| `pyjinhx/builtins/pjx_chip_input/test_pjx_chip_input_build_chip.py` | `browser/builtins/test_pjx_chip_input.py` | merge 2/2 |
| `pyjinhx/builtins/pjx_confirm_dialog/test_pjx_confirm_dialog.py` | `unit/builtins/test_pjx_confirm_dialog.py` |  |
| `pyjinhx/builtins/pjx_confirm_dialog/test_pjx_confirm_dialog_theme.py` | `browser/builtins/test_pjx_confirm_dialog.py` |  |
| `pyjinhx/builtins/pjx_divider/test_pjx_divider.py` | `unit/builtins/test_pjx_divider.py` |  |
| `pyjinhx/builtins/pjx_drawer/test_pjx_drawer.py` | `unit/builtins/test_pjx_drawer.py` |  |
| `pyjinhx/builtins/pjx_drawer/test_pjx_drawer_layer.py` | `browser/builtins/test_pjx_drawer.py` |  |
| `pyjinhx/builtins/pjx_drawer_body/test_pjx_drawer_body.py` | `unit/builtins/test_pjx_drawer_body.py` |  |
| `pyjinhx/builtins/pjx_drawer_footer/test_pjx_drawer_footer.py` | `unit/builtins/test_pjx_drawer_footer.py` |  |
| `pyjinhx/builtins/pjx_drawer_header/test_pjx_drawer_header.py` | `unit/builtins/test_pjx_drawer_header.py` |  |
| `pyjinhx/builtins/pjx_dropdown/test_pjx_dropdown.py` | `unit/builtins/test_pjx_dropdown.py` |  |
| `pyjinhx/builtins/pjx_dropdown/test_pjx_dropdown_layer.py` | `browser/builtins/test_pjx_dropdown.py` |  |
| `pyjinhx/builtins/pjx_empty_state/test_pjx_empty_state.py` | `unit/builtins/test_pjx_empty_state.py` |  |
| `pyjinhx/builtins/pjx_form_field/test_pjx_form_field.py` | `unit/builtins/test_pjx_form_field.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_form_field/test_pjx_form_field.py` | `browser/builtins/test_pjx_form_field.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph.py` | `unit/builtins/pjx_graph/test_pjx_graph.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_controls.py` | `unit/builtins/pjx_graph/test_pjx_graph_controls.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_d3_vendor.py` | `unit/builtins/pjx_graph/test_d3_vendor.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_d3_vendor.py` | `browser/builtins/pjx_graph/test_d3_vendor.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_demo.py` | `browser/builtins/pjx_graph/test_demo.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_edge_drawing.py` | `browser/builtins/pjx_graph/test_edge_drawing.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_edges.py` | `unit/builtins/pjx_graph/test_pjx_graph_edges.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_js_build.py` | `unit/builtins/pjx_graph/test_js_build.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_js_build.py` | `browser/builtins/pjx_graph/test_js_build.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_layout.py` | `browser/builtins/pjx_graph/test_layout.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_mount.py` | `browser/builtins/pjx_graph/test_mount.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_node.py` | `unit/builtins/pjx_graph/test_pjx_graph_node.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_node_drag.py` | `browser/builtins/pjx_graph/test_node_drag.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_nodes.py` | `unit/builtins/pjx_graph/test_pjx_graph_nodes.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_pan_zoom.py` | `browser/builtins/pjx_graph/test_pan_zoom.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_panel_wiring.py` | `browser/builtins/pjx_graph/test_panel_wiring.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_port_kinds.py` | `browser/builtins/pjx_graph/test_port_kinds.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_reconcile.py` | `browser/builtins/pjx_graph/test_reconcile.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_root_swap.py` | `browser/builtins/pjx_graph/test_root_swap.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_selection.py` | `browser/builtins/pjx_graph/test_selection.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_side_panel.py` | `unit/builtins/pjx_graph/test_pjx_graph_side_panel.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_theme.py` | `browser/builtins/pjx_graph/test_theme.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_wire.py` | `browser/builtins/pjx_graph/test_wire.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_wire_events.py` | `browser/builtins/pjx_graph/test_wire_events.py` |  |
| `pyjinhx/builtins/pjx_graph/test_pjx_graph_zoom_controls.py` | `browser/builtins/pjx_graph/test_zoom_controls.py` |  |
| `pyjinhx/builtins/pjx_icon/test_pjx_icon.py` | `unit/builtins/test_pjx_icon.py` | merge 1/2 |
| `pyjinhx/builtins/pjx_icon/test_pjx_icon_data.py` | `unit/builtins/test_pjx_icon.py` | merge 2/2 |
| `pyjinhx/builtins/pjx_modal/test_pjx_modal.py` | `unit/builtins/test_pjx_modal.py` |  |
| `pyjinhx/builtins/pjx_modal/test_pjx_modal_theme.py` | `browser/builtins/test_pjx_modal.py` |  |
| `pyjinhx/builtins/pjx_modal_body/test_pjx_modal_body.py` | `unit/builtins/test_pjx_modal_body.py` |  |
| `pyjinhx/builtins/pjx_modal_footer/test_pjx_modal_footer.py` | `unit/builtins/test_pjx_modal_footer.py` |  |
| `pyjinhx/builtins/pjx_modal_header/test_pjx_modal_header.py` | `unit/builtins/test_pjx_modal_header.py` |  |
| `pyjinhx/builtins/pjx_notification/test_pjx_notification.py` | `unit/builtins/test_pjx_notification.py` |  |
| `pyjinhx/builtins/pjx_password_input/test_pjx_password_input.py` | `unit/builtins/test_pjx_password_input.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_password_input/test_pjx_password_input.py` | `browser/builtins/test_pjx_password_input.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_popover/test_pjx_popover.py` | `unit/builtins/test_pjx_popover.py` | merge 1/2 |
| `pyjinhx/builtins/pjx_popover/test_pjx_popover_assets.py` | `unit/builtins/test_pjx_popover.py` | merge 2/2 |
| `pyjinhx/builtins/pjx_popover/test_pjx_popover_collision.py` | `browser/builtins/pjx_popover/test_collision.py` |  |
| `pyjinhx/builtins/pjx_popover/test_pjx_popover_layer.py` | `browser/builtins/pjx_popover/test_layer.py` |  |
| `pyjinhx/builtins/pjx_popover/test_pjx_popover_portal.py` | `browser/builtins/pjx_popover/test_portal.py` |  |
| `pyjinhx/builtins/pjx_popover/test_pjx_popover_position.py` | `browser/builtins/pjx_popover/test_position.py` |  |
| `pyjinhx/builtins/pjx_popover/test_pjx_popover_wiring.py` | `browser/builtins/pjx_popover/test_wiring.py` |  |
| `pyjinhx/builtins/pjx_popover_panel/test_pjx_popover_panel.py` | `unit/builtins/test_pjx_popover_panel.py` |  |
| `pyjinhx/builtins/pjx_popover_trigger/test_pjx_popover_trigger.py` | `unit/builtins/test_pjx_popover_trigger.py` |  |
| `pyjinhx/builtins/pjx_progress/test_pjx_progress.py` | `unit/builtins/test_pjx_progress.py` |  |
| `pyjinhx/builtins/pjx_prompt_dialog/test_pjx_prompt_dialog.py` | `unit/builtins/test_pjx_prompt_dialog.py` |  |
| `pyjinhx/builtins/pjx_prompt_dialog/test_pjx_prompt_dialog_theme.py` | `browser/builtins/test_pjx_prompt_dialog.py` |  |
| `pyjinhx/builtins/pjx_resizable_group/test_pjx_resizable_group.py` | `unit/builtins/test_pjx_resizable_group.py` |  |
| `pyjinhx/builtins/pjx_resizable_handle/test_pjx_resizable_handle.py` | `unit/builtins/test_pjx_resizable_handle.py` |  |
| `pyjinhx/builtins/pjx_resizable_panel/test_pjx_resizable_panel.py` | `unit/builtins/test_pjx_resizable_panel.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_chip.py` | `unit/builtins/pjx_roster_picker/test_pjx_roster_chip.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_item.py` | `unit/builtins/pjx_roster_picker/test_pjx_roster_item.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker.py` | `unit/builtins/pjx_roster_picker/test_pjx_roster_picker.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker.py` | `browser/builtins/pjx_roster_picker/test_theme.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_api.py` | `browser/builtins/pjx_roster_picker/test_api.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_demo.py` | `browser/builtins/pjx_roster_picker/test_demo.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_js_build.py` | `unit/builtins/pjx_roster_picker/test_js_build.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_open_close.py` | `browser/builtins/pjx_roster_picker/test_open_close.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_pick_remove.py` | `browser/builtins/pjx_roster_picker/test_pick_remove.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_placement.py` | `browser/builtins/pjx_roster_picker/test_placement.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_placement_math.py` | `browser/builtins/pjx_roster_picker/test_placement_math.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_portal.py` | `browser/builtins/pjx_roster_picker/test_portal.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_press.py` | `browser/builtins/pjx_roster_picker/test_press.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_required.py` | `browser/builtins/pjx_roster_picker/test_required.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_search.py` | `browser/builtins/pjx_roster_picker/test_search.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_swaps.py` | `browser/builtins/pjx_roster_picker/test_swaps.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_results.py` | `unit/builtins/pjx_roster_picker/test_pjx_roster_results.py` |  |
| `pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_results_lazy_paging.py` | `browser/builtins/pjx_roster_picker/test_results_lazy_paging.py` |  |
| `pyjinhx/builtins/pjx_segmented_control/test_pjx_segmented_control.py` | `unit/builtins/test_pjx_segmented_control.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_segmented_control/test_pjx_segmented_control.py` | `browser/builtins/test_pjx_segmented_control.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_select/test_pjx_select.py` | `unit/builtins/pjx_select/test_select.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_select/test_pjx_select.py` | `browser/builtins/pjx_select/test_theme.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_select/test_pjx_select_assets.py` | `unit/builtins/pjx_select/test_assets.py` |  |
| `pyjinhx/builtins/pjx_select/test_pjx_select_collision.py` | `browser/builtins/pjx_select/test_collision.py` |  |
| `pyjinhx/builtins/pjx_select/test_pjx_select_filter.py` | `unit/builtins/pjx_select/test_filter.py` |  |
| `pyjinhx/builtins/pjx_select/test_pjx_select_keyboard.py` | `unit/builtins/pjx_select/test_keyboard.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_select/test_pjx_select_keyboard.py` | `browser/builtins/pjx_select/test_keyboard.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_select/test_pjx_select_multiple.py` | `unit/builtins/pjx_select/test_multiple.py` |  |
| `pyjinhx/builtins/pjx_select/test_pjx_select_native_events.py` | `browser/builtins/pjx_select/test_native_events.py` |  |
| `pyjinhx/builtins/pjx_select/test_pjx_select_portal.py` | `browser/builtins/pjx_select/test_portal.py` |  |
| `pyjinhx/builtins/pjx_select/test_pjx_select_required.py` | `browser/builtins/pjx_select/test_required.py` |  |
| `pyjinhx/builtins/pjx_skeleton/test_pjx_skeleton.py` | `unit/builtins/test_pjx_skeleton.py` |  |
| `pyjinhx/builtins/pjx_spinner/test_pjx_spinner.py` | `unit/builtins/test_pjx_spinner.py` |  |
| `pyjinhx/builtins/pjx_stack/test_pjx_stack.py` | `unit/builtins/test_pjx_stack.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_stack/test_pjx_stack.py` | `browser/builtins/test_pjx_stack.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_tab/test_pjx_tab.py` | `unit/builtins/test_pjx_tab.py` |  |
| `pyjinhx/builtins/pjx_tab_group/test_pjx_tab_group.py` | `unit/builtins/test_pjx_tab_group.py` | merge 1/2 |
| `pyjinhx/builtins/pjx_tab_group/test_pjx_tab_group_composition.py` | `unit/builtins/test_pjx_tab_group.py` | merge 2/2 |
| `pyjinhx/builtins/pjx_tab_list/test_pjx_tab_list.py` | `unit/builtins/test_pjx_tab_list.py` |  |
| `pyjinhx/builtins/pjx_tab_panel/test_pjx_tab_panel.py` | `unit/builtins/test_pjx_tab_panel.py` |  |
| `pyjinhx/builtins/pjx_toast_host/test_pjx_toast_host.py` | `unit/builtins/test_pjx_toast_host.py` |  |
| `pyjinhx/builtins/pjx_toggle_switch/test_pjx_toggle_switch.py` | `unit/builtins/test_pjx_toggle_switch.py` | split: non-browser tests stay |
| `pyjinhx/builtins/pjx_toggle_switch/test_pjx_toggle_switch.py` | `browser/builtins/test_pjx_toggle_switch.py` | split: browser tests (4.3) |
| `pyjinhx/builtins/pjx_tooltip/test_pjx_tooltip.py` | `unit/builtins/test_pjx_tooltip.py` |  |
| `pyjinhx/builtins/pjx_tooltip/test_pjx_tooltip_backdrop.py` | `browser/builtins/pjx_tooltip/test_backdrop.py` |  |
| `pyjinhx/builtins/pjx_tooltip/test_pjx_tooltip_collision.py` | `browser/builtins/pjx_tooltip/test_collision.py` |  |
| `pyjinhx/builtins/pjx_tooltip/test_pjx_tooltip_dialog.py` | `browser/builtins/pjx_tooltip/test_dialog.py` |  |
| `pyjinhx/builtins/pjx_tooltip/test_pjx_tooltip_layer.py` | `browser/builtins/pjx_tooltip/test_layer.py` |  |
| `pyjinhx/builtins/pjx_tooltip_content/test_pjx_tooltip_content.py` | `unit/builtins/test_pjx_tooltip_content.py` |  |
| `pyjinhx/builtins/pjx_tooltip_trigger/test_pjx_tooltip_trigger.py` | `unit/builtins/test_pjx_tooltip_trigger.py` |  |
| `pyjinhx/builtins/test_builtin_autoregistration.py` | `unit/builtins/test_builtins.py` | merge 2/2 |
| `pyjinhx/builtins/test_family_composed_shells_sweep.py` | `unit/builtins/families/test_composed_shells.py` |  |
| `pyjinhx/builtins/test_family_data_htmx_sweep.py` | `unit/builtins/families/test_data_htmx.py` |  |
| `pyjinhx/builtins/test_family_display_primitives_sweep.py` | `unit/builtins/families/test_display_primitives.py` |  |
| `pyjinhx/builtins/test_family_forms_sweep.py` | `unit/builtins/families/test_forms.py` |  |
| `pyjinhx/builtins/test_family_js_heavy_sweep.py` | `unit/builtins/families/test_js_heavy.py` |  |
| `pyjinhx/builtins/test_feedback_theme_tokens.py` | `unit/builtins/theme_tokens/test_feedback.py` |  |
| `pyjinhx/builtins/test_navigation_theme_tokens.py` | `unit/builtins/theme_tokens/test_navigation.py` |  |
| `pyjinhx/builtins/test_pjx_lazy_load.py` | `unit/builtins/test_pjx_lazy_load.py` |  |
| `pyjinhx/builtins/test_pjx_page_loader.py` | `unit/builtins/test_pjx_page_loader.py` |  |
| `pyjinhx/builtins/test_pjx_paginator.py` | `unit/builtins/test_pjx_paginator.py` |  |
| `pyjinhx/builtins/test_pjx_region_loader.py` | `unit/builtins/test_pjx_region_loader.py` |  |
| `pyjinhx/builtins/test_pjx_table.py` | `unit/builtins/test_pjx_table.py` |  |
| `pyjinhx/builtins/test_pjx_table_body.py` | `unit/builtins/test_pjx_table_body.py` |  |
| `pyjinhx/builtins/test_pjx_table_cell.py` | `unit/builtins/test_pjx_table_cell.py` |  |
| `pyjinhx/builtins/test_pjx_table_head.py` | `unit/builtins/test_pjx_table_head.py` |  |
| `pyjinhx/builtins/test_pjx_table_header_cell.py` | `unit/builtins/test_pjx_table_header_cell.py` |  |
| `pyjinhx/builtins/test_pjx_table_row.py` | `unit/builtins/test_pjx_table_row.py` |  |
| `pyjinhx/client/test_client_package.py` | `unit/client/test_client.py` | merge 1/3 |
| `pyjinhx/client/test_inject.py` | `unit/client/test_inject.py` | merge 1/3 |
| `pyjinhx/client/test_loading_artifacts.py` | `browser/client/test_loading_artifacts.py` |  |
| `pyjinhx/client/test_page_loader_namespace.py` | `browser/client/test_page_loader_namespace.py` |  |
| `pyjinhx/client/test_pjx_assets_scan.py` | `browser/client/test_assets_scan.py` |  |
| `pyjinhx/client/test_pjx_head_assets.py` | `browser/client/test_head_assets.py` |  |
| `pyjinhx/client/test_pjx_head_assets_detached.py` | `browser/client/test_head_assets_detached.py` |  |
| `pyjinhx/client/test_pjx_headers.py` | `browser/client/test_headers.py` |  |
| `pyjinhx/client/test_pjx_htmx_guard.py` | `browser/client/test_htmx_guard.py` |  |
| `pyjinhx/client/test_pjx_loader_api.py` | `browser/client/test_loader_api.py` |  |
| `pyjinhx/client/test_pjx_loading.py` | `browser/client/test_loading.py` |  |
| `pyjinhx/client/test_pjx_loading_events.py` | `browser/client/test_loading_events.py` |  |
| `pyjinhx/client/test_pjx_manifest.py` | `browser/client/test_manifest.py` |  |
| `pyjinhx/client/test_pjx_namespace_merge.py` | `browser/client/test_namespace_merge.py` |  |
| `pyjinhx/client/test_pjx_promote_assets.py` | `browser/client/test_promote_assets.py` |  |
| `pyjinhx/client/test_pjx_style.py` | `unit/client/test_inject.py` | merge 2/3 |
| `pyjinhx/client/test_pjx_theme.py` | `unit/client/test_client.py` | merge 2/3 |
| `pyjinhx/client/test_pjx_theme_inject.py` | `unit/client/test_inject.py` | split: non-browser tests stay; merge 3/3 |
| `pyjinhx/client/test_pjx_theme_inject.py` | `browser/client/test_theme.py` | split: browser tests (4.3) |
| `pyjinhx/client/test_pjx_toast.py` | `browser/client/test_toast.py` |  |
| `pyjinhx/client/test_pjx_trigger.py` | `browser/client/test_trigger.py` |  |
| `pyjinhx/client/test_runtime_bundle_e2e.py` | `browser/client/test_runtime_bundle_e2e.py` |  |
| `pyjinhx/client/test_vendored_htmx.py` | `unit/client/test_client.py` | merge 3/3 |
| `pyjinhx/integrations/test_base.py` | `unit/integrations/test_base.py` | merge 1/2 |
| `pyjinhx/integrations/test_diskcache_wiring.py` | `unit/integrations/test_diskcache.py` |  |
| `pyjinhx/integrations/test_fastapi_wiring.py` | `unit/integrations/fastapi/test_wiring.py` |  |
| `pyjinhx/integrations/test_reactive_request_cycle.py` | `unit/integrations/fastapi/test_request_cycle.py` |  |
| `pyjinhx/integrations/test_registry.py` | `unit/integrations/test_base.py` | merge 2/2 |
| `pyjinhx/reactive/test_fanout_assets.py` | `unit/reactive/test_assets.py` |  |
| `pyjinhx/reactive/test_load_cost.py` | `unit/reactive/test_load_cost.py` |  |
| `pyjinhx/reactive/test_reactive_cache.py` | `unit/reactive/cache/test_cache.py` |  |
| `pyjinhx/reactive/test_reactive_cache_backend.py` | `unit/reactive/test_backend.py` |  |
| `pyjinhx/reactive/test_reactive_cache_backend_health.py` | `unit/reactive/test_backend_health.py` |  |
| `pyjinhx/reactive/test_reactive_cache_failure_policy.py` | `unit/reactive/cache/test_failure_policy.py` |  |
| `pyjinhx/reactive/test_reactive_cache_key.py` | `unit/reactive/component/test_cache_key.py` |  |
| `pyjinhx/reactive/test_reactive_cache_seam.py` | `unit/reactive/cache/test_seam.py` |  |
| `pyjinhx/reactive/test_reactive_cache_tier2_wiring.py` | `unit/reactive/cache/test_tier2_wiring.py` |  |
| `pyjinhx/reactive/test_reactive_component.py` | `unit/reactive/component/test_load_wrap.py` |  |
| `pyjinhx/reactive/test_reactive_fanout.py` | `unit/reactive/test_fanout.py` |  |
| `pyjinhx/reactive/test_reactive_keys.py` | `unit/reactive/test_keys.py` |  |
| `pyjinhx/reactive/test_reactive_mount.py` | `unit/reactive/component/test_mount.py` |  |
| `pyjinhx/reactive/test_reactive_mutations.py` | `unit/reactive/test_mutations.py` |  |
| `pyjinhx/reactive/test_reactive_root_attrs.py` | `unit/reactive/test_root_attrs.py` |  |
| `pyjinhx/reactive/test_reactive_state_hash.py` | `unit/reactive/component/test_state_hash.py` |  |
| `pyjinhx/reactive/test_tier2_nested_ownership.py` | `unit/reactive/cache/test_tier2_nested_ownership.py` |  |
| `pyjinhx/test_app_context.py` | `unit/test_app_context.py` |  |
| `pyjinhx/test_asset_emission.py` | `unit/assets/test_emission.py` |  |
| `pyjinhx/test_asset_hashing.py` | `unit/assets/test_hashing.py` |  |
| `pyjinhx/test_asset_manifest.py` | `unit/assets/test_manifest.py` |  |
| `pyjinhx/test_assets.py` | `unit/assets/test_accumulation.py` |  |
| `pyjinhx/test_bench_script_v2.py` | `scripts/test_bench.py` | merge 2/3 |
| `pyjinhx/test_block_discovery.py` | `unit/discovery/test_python_documents.py` |  |
| `pyjinhx/test_block_grammar_corpus.py` | `unit/test_template_blocks.py` | merge 2/2 |
| `pyjinhx/test_children_field_resolution.py` | `unit/component/test_children_field.py` |  |
| `pyjinhx/test_classless_factory.py` | `unit/classless/test_factory.py` |  |
| `pyjinhx/test_classless_matrix.py` | `unit/classless/test_surface.py` |  |
| `pyjinhx/test_component.py` | `unit/component/test_base_component.py` |  |
| `pyjinhx/test_component_descriptor.py` | `unit/component/test_class_descriptor.py` |  |
| `pyjinhx/test_component_export_not_shadowed.py` | `packaging/test_package_layout.py` | merge 2/2 |
| `pyjinhx/test_compose_fanout.py` | `unit/test_responses.py` | merge 2/2 |
| `pyjinhx/test_concurrency.py` | `unit/session/test_concurrency.py` |  |
| `pyjinhx/test_config_v2.py` | `unit/test_config.py` |  |
| `pyjinhx/test_context.py` | `unit/test_context.py` |  |
| `pyjinhx/test_descriptor.py` | `unit/test_descriptor.py` |  |
| `pyjinhx/test_dev.py` | `unit/test_dev.py` |  |
| `pyjinhx/test_direct_nesting.py` | `unit/slots/test_direct_nesting.py` |  |
| `pyjinhx/test_discovery.py` | `unit/discovery/test_walk.py` |  |
| `pyjinhx/test_discovery_matrix.py` | `unit/discovery/test_combined.py` |  |
| `pyjinhx/test_docs_api_boundary.py` | `docs/test_api_boundary.py` |  |
| `pyjinhx/test_docs_cache_backends.py` | `docs/test_cache_backends.py` |  |
| `pyjinhx/test_docs_chart.py` | `docs/test_chart.py` |  |
| `pyjinhx/test_docs_reference_real_fields.py` | `docs/test_reference_real_fields.py` |  |
| `pyjinhx/test_docs_roster_picker.py` | `docs/test_roster_picker.py` |  |
| `pyjinhx/test_docs_theme_migration.py` | `docs/test_theme_migration.py` |  |
| `pyjinhx/test_fewer_files_parity.py` | `apps/fewer_files/test_parity.py` |  |
| `pyjinhx/test_fewer_files_startup.py` | `apps/fewer_files/test_startup.py` |  |
| `pyjinhx/test_gallery_demos.py` | `docs/test_gallery_demos.py` |  |
| `pyjinhx/test_gallery_theme_toggle_browser.py` | `browser/test_gallery_theme_toggle.py` |  |
| `pyjinhx/test_import_graph.py` | `packaging/test_import_graph.py` |  |
| `pyjinhx/test_importer.py` | `unit/test_importer.py` |  |
| `pyjinhx/test_instance_registry.py` | `unit/test_registry.py` |  |
| `pyjinhx/test_loader.py` | `unit/session/test_loader.py` |  |
| `pyjinhx/test_manifest.py` | `unit/test_manifest.py` |  |
| `pyjinhx/test_markers.py` | `unit/test_markers.py` |  |
| `pyjinhx/test_orphan_tags.py` | `unit/classless/test_orphan_tags.py` |  |
| `pyjinhx/test_pjx_python_component.py` | `unit/sfc/test_pjx_document.py` |  |
| `pyjinhx/test_props_header_build.py` | `unit/test_props_header.py` | merge 2/2 |
| `pyjinhx/test_props_header_parse.py` | `unit/test_props_header.py` | merge 1/2 |
| `pyjinhx/test_registry.py` | `unit/discovery/test_registry.py` |  |
| `pyjinhx/test_render_cache_behavior.py` | `unit/render_cache/test_behavior.py` |  |
| `pyjinhx/test_render_cache_key.py` | `unit/render_cache/test_key.py` |  |
| `pyjinhx/test_render_cache_store.py` | `unit/render_cache/test_store.py` |  |
| `pyjinhx/test_render_cache_wiring.py` | `unit/render_cache/test_wiring.py` |  |
| `pyjinhx/test_render_children.py` | `unit/rendering/test_children.py` |  |
| `pyjinhx/test_render_context.py` | `unit/test_render_context.py` |  |
| `pyjinhx/test_render_cost_threshold.py` | `unit/render_cache/test_cost_threshold.py` |  |
| `pyjinhx/test_render_cycle_guard.py` | `unit/rendering/test_cycle_guard.py` |  |
| `pyjinhx/test_render_hook.py` | `unit/rendering/test_hook.py` |  |
| `pyjinhx/test_render_instantiate.py` | `unit/rendering/test_instantiate.py` |  |
| `pyjinhx/test_render_integration.py` | `unit/rendering/test_integration.py` |  |
| `pyjinhx/test_render_level.py` | `unit/rendering/test_level.py` |  |
| `pyjinhx/test_render_nested_integration.py` | `unit/rendering/test_nested_integration.py` |  |
| `pyjinhx/test_render_public.py` | `unit/rendering/test_public.py` |  |
| `pyjinhx/test_render_splice.py` | `unit/rendering/test_splice.py` |  |
| `pyjinhx/test_replace.py` | `unit/discovery/test_replace.py` |  |
| `pyjinhx/test_responses.py` | `unit/test_responses.py` | merge 1/2 |
| `pyjinhx/test_root_attrs.py` | `unit/test_root_attrs.py` |  |
| `pyjinhx/test_segments.py` | `unit/segments/test_segments.py` |  |
| `pyjinhx/test_segments_fastpath.py` | `unit/segments/test_fastpath.py` |  |
| `pyjinhx/test_session.py` | `unit/session/test_session.py` |  |
| `pyjinhx/test_setup_backend_dispatch.py` | `unit/integrations/test_setup_dispatch.py` |  |
| `pyjinhx/test_sfc_component.py` | `unit/sfc/test_inline_component.py` |  |
| `pyjinhx/test_sfc_extract.py` | `unit/sfc/test_extract.py` |  |
| `pyjinhx/test_sfc_header.py` | `unit/sfc/test_header.py` |  |
| `pyjinhx/test_sfc_python_block.py` | `unit/sfc/test_python_block.py` |  |
| `pyjinhx/test_slot_collections.py` | `unit/slots/test_collections.py` |  |
| `pyjinhx/test_slot_props_view.py` | `unit/slots/test_props_view.py` |  |
| `pyjinhx/test_slot_semantics_matrix.py` | `unit/slots/test_semantics.py` |  |
| `pyjinhx/test_slot_type_v2.py` | `unit/slots/test_slot_type.py` |  |
| `pyjinhx/test_stale_header_warning.py` | `unit/rendering/test_stale_header_warning.py` |  |
| `pyjinhx/test_stubgen.py` | `unit/test_stubgen.py` |  |
| `pyjinhx/test_template_blocks.py` | `unit/test_template_blocks.py` | merge 1/2 |
| `pyjinhx/test_theme_tokens.py` | `unit/builtins/theme_tokens/test_stylesheets.py` |  |
| `test_bench_fixture_parity.py` | `scripts/test_bench.py` | merge 3/3 |
| `test_bench_scripts_smoke.py` | `scripts/test_bench.py` | merge 1/3 |
| `test_builtin_extra_attrs.py` | `unit/builtins/test_builtins.py` | merge 1/2 |
| `test_fold_script.py` | `scripts/test_fold_components.py` |  |
| `test_package_layout.py` | `packaging/test_package_layout.py` | merge 1/2 |
| `test_theme_token_reference.py` | `docs/test_theme_token_reference.py` |  |
| `test_theming_guide.py` | `docs/test_theming_guide.py` |  |

### 2.2 Merges

| Merged file | Sources, in order | Lines | Tests |
|---|---|---|---|
| `browser/builtins/test_pjx_chip_input.py` | `test_pjx_chip_input.py#B` + `test_pjx_chip_input_build_chip.py` | 149 | 5 |
| `packaging/test_package_layout.py` | `test_package_layout.py` + `test_component_export_not_shadowed.py` | 351 | 25 |
| `scripts/test_bench.py` | `test_bench_scripts_smoke.py` + `test_bench_script_v2.py` + `test_bench_fixture_parity.py` | 201 | 32 |
| `unit/builtins/test_builtins.py` | `test_builtin_extra_attrs.py` + `test_builtin_autoregistration.py` | 134 | 5 |
| `unit/builtins/test_pjx_chart.py` | `test_pjx_chart.py` + `test_pjx_chart_scale.py` | 393 | 61 |
| `unit/builtins/test_pjx_icon.py` | `test_pjx_icon.py` + `test_pjx_icon_data.py` | 150 | 15 |
| `unit/builtins/test_pjx_popover.py` | `test_pjx_popover.py` + `test_pjx_popover_assets.py` | 136 | 16 |
| `unit/builtins/test_pjx_tab_group.py` | `test_pjx_tab_group.py` + `test_pjx_tab_group_composition.py` | 125 | 11 |
| `unit/client/test_client.py` | `test_client_package.py` + `test_pjx_theme.py` + `test_vendored_htmx.py` | 275 | 25 |
| `unit/client/test_inject.py` | `test_inject.py` + `test_pjx_style.py` + `test_pjx_theme_inject.py#U` | 520 | 62 |
| `unit/integrations/test_base.py` | `test_base.py` + `test_registry.py` | 253 | 15 |
| `unit/test_props_header.py` | `test_props_header_parse.py` + `test_props_header_build.py` | 734 | 118 |
| `unit/test_responses.py` | `test_responses.py` + `test_compose_fanout.py` | 539 | 40 |
| `unit/test_template_blocks.py` | `test_template_blocks.py` + `test_block_grammar_corpus.py` | 651 | 138 |

`#B` marks the browser tests split out of a mixed file. All fourteen merges were
trial-built in a scratch directory (sources concatenated in the order shown) and run:
each collects exactly the sum of its sources and passes. One planned merge failed that
trial and was dropped: `test_setup_backend_dispatch.py` into `unit/test_config.py`. Its
autouse `_empty_backend_registry` empties the integrations backend slot for every test
in the file, which breaks `test_setup_delegates_an_asgi_app_to_the_fastapi_integration`
from `test_config_v2.py`. It becomes `unit/integrations/test_setup_dispatch.py` instead.

Renames needed inside merged files:

| Merged file | Name | What to do |
|---|---|---|
| `unit/test_responses.py` | `_compose` | Defined in both sources with the same body and a different docstring. Keep the first, delete the second. |
| `unit/client/test_inject.py` | `FakeRequest` | Identical in `test_inject.py` and `test_pjx_theme_inject.py`. Keep one. |

No two sources of any merge share a test function name, a test class name or any other
top-level name beyond the two above (checked by parsing every source; the trial's
collected counts equal the sums). Duplicate imports are expected and are what
`ruff check` will list as F811 until they are folded together.

`from __future__ import annotations`: every merge has sources that agree on it, except
`browser/builtins/test_pjx_chip_input.py`. Keep the import there, because
`test_pjx_chip_input_build_chip.py` annotates with `Page`, which it imports only under
`TYPE_CHECKING`.

### 2.3 Conftests, helpers and files beside tests

| Old path (under `tests/`) | New path (under `tests/`) |
|---|---|
| `pyjinhx/conftest.py` | `conftest.py` |
| `examples/conftest.py` | `apps/todo/conftest.py` |
| `pyjinhx/client/conftest.py` | `browser/client/conftest.py` (+ `_require_chromium` -> browser/conftest.py) |
| `pyjinhx/builtins/pjx_chart/conftest.py` | (deleted: both fixtures -> browser/conftest.py) |
| `pyjinhx/builtins/pjx_graph/conftest.py` | `unit/builtins/pjx_graph/conftest.py` (browser fixtures split out, see section 4) |
| `pyjinhx/builtins/pjx_roster_picker/conftest.py` | `unit/builtins/pjx_roster_picker/conftest.py` (browser fixtures split out, see section 4) |
| `pyjinhx/client/__init__.py` | (deleted) |
| `pyjinhx/integrations/__init__.py` | (deleted) |
| `pyjinhx/header_names.py` | `fixtures/header_names.py` |
| `pyjinhx/header_import_probe.py` | `fixtures/header_import_probe.py` |
| `pyjinhx/stale_card.pjx` | `unit/rendering/stale_card.pjx` (stays beside its test, see section 7) |
| `pyjinhx/stale_badge.pjx` | `unit/rendering/stale_badge.pjx` (stays beside its test, see section 7) |
| `pyjinhx/broken_demo.pjx` | `docs/broken_demo.pjx` (stays beside its test, see section 7) |
| `fixtures/__init__.py` | `fixtures/__init__.py` |
| `fixtures/bench_builtin_heavy.py` | `fixtures/bench/bench_builtin_heavy.py` |
| `fixtures/bench_page.pjx` | `fixtures/bench/bench_page.pjx` |
| `fixtures/bench_multi.pjx` | `fixtures/bench/bench_multi.pjx` |

One empty `__init__.py` is added (`tests/fixtures/bench/__init__.py`) and two are
removed (`tests/pyjinhx/client/__init__.py`, `tests/pyjinhx/integrations/__init__.py`;
section 5.1 explains why they are no longer needed).

### 2.4 Template fixtures

`tests/templates/discovery/` (10 files) moves as a whole to
`tests/fixtures/templates/discovery/`; its internal shape is the fixture, so nothing
inside it is regrouped. Every other template keeps its file name and moves into a
topic folder:

| Old path (under `tests/templates/`) | New path (under `tests/fixtures/templates/`) | Referenced by (old names) |
|---|---|---|
| `bad.html` | `basic/bad.html` | test_render_level.py, test_render_public.py |
| `broken_assertion.html` | `basic/broken_assertion.html` | test_render_level.py |
| `card.html` | `basic/card.html` | test_render_level.py |
| `child_button.html` | `basic/child_button.html` | test_render_level.py |
| `child_card.html` | `basic/child_card.html` | test_render_level.py |
| `child_icon.html` | `basic/child_icon.html` | test_render_level.py |
| `container.html` | `basic/container.html` | test_reactive_mount.py, test_render_level.py |
| `container_only_plain.html` | `reactive/container_only_plain.html` | test_reactive_mount.py |
| `cycle_a.html` | `cycle/cycle_a.html` | test_render_cycle_guard.py |
| `cycle_acyclic_a.html` | `cycle/cycle_acyclic_a.html` | test_render_cycle_guard.py |
| `cycle_acyclic_b.html` | `cycle/cycle_acyclic_b.html` | test_render_cycle_guard.py |
| `cycle_acyclic_c.html` | `cycle/cycle_acyclic_c.html` | test_render_cycle_guard.py |
| `cycle_b.html` | `cycle/cycle_b.html` | test_render_cycle_guard.py |
| `cycle_badge.css` | `fastapi/cycle_badge.css` | test_reactive_request_cycle.py |
| `cycle_badge.js` | `fastapi/cycle_badge.js` | test_reactive_request_cycle.py |
| `cycle_badge.pjx` | `fastapi/cycle_badge.pjx` | test_reactive_request_cycle.py |
| `cycle_card.pjx` | `fastapi/cycle_card.pjx` | test_reactive_request_cycle.py |
| `cycle_card_l2.html` | `cycle/cycle_card_l2.html` | test_render_cycle_guard.py |
| `cycle_diamond.html` | `cycle/cycle_diamond.html` | test_render_cycle_guard.py |
| `cycle_long_a.html` | `cycle/cycle_long_a.html` | test_render_cycle_guard.py |
| `cycle_long_b.html` | `cycle/cycle_long_b.html` | test_render_cycle_guard.py |
| `cycle_long_c.html` | `cycle/cycle_long_c.html` | test_render_cycle_guard.py |
| `cycle_nested.pjx` | `fastapi/cycle_nested.pjx` | test_reactive_request_cycle.py |
| `cycle_passthrough.html` | `cycle/cycle_passthrough.html` | test_render_cycle_guard.py |
| `cycle_row_l2.html` | `cycle/cycle_row_l2.html` | test_render_cycle_guard.py |
| `cycle_self.html` | `cycle/cycle_self.html` | test_render_cycle_guard.py |
| `cycle_shell.pjx` | `fastapi/cycle_shell.pjx` | test_reactive_request_cycle.py |
| `div.html` | `basic/div.html` | test_asset_emission.py, test_assets.py, test_concurrency.py, test_render_level.py, test_render_public.py, test_session.py, test_slot_type_v2.py |
| `empty.html` | `basic/empty.html` | test_render_level.py, test_render_public.py |
| `icon.html` | `basic/icon.html` | test_render_cache_wiring.py, test_render_level.py |
| `inner_badge.html` | `reactive/inner_badge.html` | test_reactive_root_attrs.py |
| `integration_attrs.html` | `integration/integration_attrs.html` | test_render_integration.py |
| `integration_childless.html` | `integration/integration_childless.html` | test_render_integration.py |
| `integration_escape.html` | `integration/integration_escape.html` | test_render_integration.py |
| `integration_full.html` | `integration/integration_full.html` | test_render_integration.py |
| `integration_slot.html` | `integration/integration_slot.html` | test_render_integration.py |
| `lowercase.html` | `basic/lowercase.html` | test_render_level.py |
| `middle_wrap.html` | `reactive/middle_wrap.html` | test_reactive_root_attrs.py |
| `minimal.html` | `basic/minimal.html` | test_render_level.py |
| `mixedcase.html` | `basic/mixedcase.html` | test_render_level.py |
| `nest_attr.html` | `nesting/nest_attr.html` | test_direct_nesting.py |
| `nest_content.html` | `nesting/nest_content.html` | test_direct_nesting.py, test_slot_props_view.py, test_slot_semantics_matrix.py, test_slot_type_v2.py |
| `nest_if.html` | `nesting/nest_if.html` | test_direct_nesting.py, test_slot_semantics_matrix.py |
| `nest_leaf.html` | `nesting/nest_leaf.html` | test_direct_nesting.py, test_slot_semantics_matrix.py |
| `nest_wrap.html` | `nesting/nest_wrap.html` | test_direct_nesting.py, test_slot_collections.py, test_slot_props_view.py |
| `nested.html` | `basic/nested.html` | test_render_level.py |
| `nested_bad_leaf.html` | `nesting/nested_bad_leaf.html` | test_render_nested_integration.py |
| `nested_bad_mid.html` | `nesting/nested_bad_mid.html` | test_render_nested_integration.py |
| `nested_bad_root.html` | `nesting/nested_bad_root.html` | test_render_nested_integration.py |
| `nested_branches.html` | `nesting/nested_branches.html` | test_render_nested_integration.py |
| `nested_emit_parent.html` | `nesting/nested_emit_parent.html` | test_asset_emission.py |
| `nested_full_mid.html` | `nesting/nested_full_mid.html` | test_render_nested_integration.py |
| `nested_full_root.html` | `nesting/nested_full_root.html` | test_render_nested_integration.py |
| `nested_leaf.html` | `nesting/nested_leaf.html` | test_render_hook.py, test_render_nested_integration.py |
| `nested_loop.html` | `nesting/nested_loop.html` | test_render_nested_integration.py |
| `nested_mid.html` | `nesting/nested_mid.html` | test_render_hook.py, test_render_nested_integration.py |
| `nested_mixed_mid.html` | `nesting/nested_mixed_mid.html` | test_render_nested_integration.py |
| `nested_mixed_root.html` | `nesting/nested_mixed_root.html` | test_render_nested_integration.py |
| `nested_root.html` | `nesting/nested_root.html` | test_render_hook.py, test_render_nested_integration.py |
| `pjx_integrations_greeting.html` | `fastapi/pjx_integrations_greeting.html` | test_fastapi_wiring.py |
| `plain_div.html` | `basic/plain_div.html` | test_asset_emission.py, test_assets.py, test_session.py |
| `plain_widget.html` | `reactive/plain_widget.html` | test_reactive_mount.py, test_reactive_root_attrs.py |
| `reactive_attrs.html` | `reactive/reactive_attrs.html` | test_reactive_root_attrs.py |
| `reactive_builtin_root.html` | `reactive/reactive_builtin_root.html` | test_reactive_root_attrs.py |
| `reactive_double_root.html` | `reactive/reactive_double_root.html` | test_reactive_root_attrs.py |
| `reactive_inner_root.html` | `reactive/reactive_inner_root.html` | test_reactive_root_attrs.py |
| `reactive_keyed_json_attr.html` | `reactive/reactive_keyed_json_attr.html` | test_reactive_mount.py |
| `reactive_keyed_list_widget.html` | `reactive/reactive_keyed_list_widget.html` | test_reactive_mount.py |
| `reactive_keyed_override.html` | `reactive/reactive_keyed_override.html` | test_reactive_mount.py |
| `reactive_keyed_twice.html` | `reactive/reactive_keyed_twice.html` | test_reactive_mount.py |
| `reactive_keyed_widget.html` | `reactive/reactive_keyed_widget.html` | test_reactive_mount.py |
| `reactive_mount_container.html` | `reactive/reactive_mount_container.html` | test_reactive_mount.py |
| `reactive_nested_reactive_root.html` | `reactive/reactive_nested_reactive_root.html` | test_reactive_root_attrs.py |
| `reactive_prestamped.html` | `reactive/reactive_prestamped.html` | test_reactive_root_attrs.py |
| `reactive_prologue_root.html` | `reactive/reactive_prologue_root.html` | test_reactive_root_attrs.py |
| `reactive_shell.html` | `reactive/reactive_shell.html` | test_reactive_root_attrs.py |
| `reactive_void.html` | `reactive/reactive_void.html` | test_reactive_root_attrs.py |
| `reactive_widget.html` | `reactive/reactive_widget.html` | test_reactive_mount.py, test_reactive_root_attrs.py, test_instance_registry.py |
| `roundtrip.html` | `basic/roundtrip.html` | test_render_level.py, test_render_public.py |
| `slot_dict.html` | `slots/slot_dict.html` | test_slot_collections.py, test_slot_semantics_matrix.py |
| `slot_header_content.html` | `slots/slot_header_content.html` | test_slot_semantics_matrix.py |
| `slot_if.html` | `slots/slot_if.html` | test_slot_collections.py, test_slot_props_view.py, test_slot_type_v2.py |
| `slot_interp.html` | `slots/slot_interp.html` | test_render_level.py, test_slot_collections.py, test_slot_props_view.py, test_slot_type_v2.py |
| `slot_leaf.html` | `slots/slot_leaf.html` | test_render_level.py, test_slot_collections.py, test_slot_props_view.py, test_slot_semantics_matrix.py, test_slot_type_v2.py |
| `slot_list.html` | `slots/slot_list.html` | test_slot_collections.py, test_slot_semantics_matrix.py |
| `slot_list_len.html` | `slots/slot_list_len.html` | test_slot_collections.py, test_slot_semantics_matrix.py |
| `slot_mixed_kinds.html` | `slots/slot_mixed_kinds.html` | test_slot_semantics_matrix.py |
| `slot_props.html` | `slots/slot_props.html` | test_slot_props_view.py, test_slot_semantics_matrix.py |
| `slot_props_bare_view.html` | `slots/slot_props_bare_view.html` | test_slot_props_view.py |
| `slot_props_dict.html` | `slots/slot_props_dict.html` | test_slot_props_view.py, test_slot_semantics_matrix.py |
| `slot_props_list.html` | `slots/slot_props_list.html` | test_slot_props_view.py, test_slot_semantics_matrix.py |
| `slotted.html` | `slots/slotted.html` | test_render_level.py |
| `splice_bad_child.html` | `splice/splice_bad_child.html` | test_render_splice.py |
| `splice_bad_parent.html` | `splice/splice_bad_parent.html` | test_render_splice.py |
| `splice_child.html` | `splice/splice_child.html` | test_render_splice.py |
| `splice_mixed.html` | `splice/splice_mixed.html` | test_render_splice.py |
| `splice_parent.html` | `splice/splice_parent.html` | test_render_splice.py |
| `splice_plain.html` | `splice/splice_plain.html` | test_render_splice.py |
| `splice_siblings.html` | `splice/splice_siblings.html` | test_render_splice.py |
| `stale_render.html` | `basic/stale_render.html` | test_stale_header_warning.py |
| `test.html` | `basic/test.html` | test_render_level.py |
| `unknown_host.html` | `basic/unknown_host.html` | test_render_children.py |
| `unsafe.html` | `basic/unsafe.html` | test_render_level.py |

`cycle_*.html` are the render cycle guard's templates. `cycle_badge`, `cycle_card`,
`cycle_nested` and `cycle_shell` belong to the FastAPI request cycle test despite the
shared prefix, so they sit in `fastapi/` with `cycle_badge.css` and `cycle_badge.js`,
which must stay beside `cycle_badge.pjx`.

### 2.5 Fixtures that do not move

- `tests/fixtures/__init__.py`
- `tests/fixtures/block_grammar/` (81 files)
- `tests/fixtures/fewer_files/` (96 files)

## 3. References that must change

### 3.1 Dotted module names

`tests/fixtures/fewer_files` does not move, so none of the `tests.fixtures.fewer_files...`
names inside its `.py` files, `{#python` blocks and `{#def` headers change (41
occurrences in 25 files), and neither do the ones in `test_fewer_files_parity.py`, which
anchors on `tests.fixtures.fewer_files.__file__` rather than on its own location. No
`tests/__init__.py` is added: `tests` stays the namespace package it is today, importable
because the editable install puts the repo root on `sys.path`.

These do change:

| File:line (old path) | Old | New |
|---|---|---|
| `tests/pyjinhx/test_block_discovery.py:18` | `from tests.pyjinhx.conftest import Write` | `from tests.conftest import Write` |
| `tests/pyjinhx/test_importer.py:17` | `from tests.pyjinhx.conftest import Write` | `from tests.conftest import Write` |
| `tests/pyjinhx/test_props_header_build.py:20` | `from tests.pyjinhx import header_names` | `from tests.fixtures import header_names` |
| `tests/pyjinhx/test_props_header_build.py:271, 283, 302, 308, 309, 323, 334, 335, 362` | `tests.pyjinhx.header_names.` (inside strings) | `tests.fixtures.header_names.` |
| `tests/pyjinhx/test_props_header_build.py:291` | `"tests.pyjinhx.header_import_probe"` | `"tests.fixtures.header_import_probe"` |
| `tests/pyjinhx/test_props_header_parse.py:363` | `"tests.pyjinhx.header_import_probe"` | `"tests.fixtures.header_import_probe"` |
| `tests/pyjinhx/test_classless_factory.py:529` | `tests.pyjinhx.header_names.PAGE_SIZE` (inside a `{#def` string) | `tests.fixtures.header_names.PAGE_SIZE` |
| `tests/test_bench_fixture_parity.py:17` | `from tests.fixtures.bench_builtin_heavy import (` | `from tests.fixtures.bench.bench_builtin_heavy import (` |

One sed covers the header names: `s/tests\.pyjinhx\.header_/tests.fixtures.header_/g` over
`tests/`. Afterwards `git grep -n 'tests\.pyjinhx' -- tests` must print nothing.

### 3.2 Paths computed from `__file__`

The index in `parents[N]` counts folders between the file and the target, so it
changes with the file's new depth. Rows whose expression comes out identical (most of
`pjx_graph/`, `pjx_roster_picker/` and `pjx_select/`, which stay four folders deep)
are left out. A mixed file's row applies to both halves.

| Old file:line | New file | Old expression | New expression |
|---|---|---|---|
| `pyjinhx/builtins/pjx_chart/test_pjx_chart_browser.py:23` | `browser/builtins/test_pjx_chart.py` | `Path(__file__).resolve().parents[4]` | `Path(__file__).resolve().parents[3]` |
| `pyjinhx/builtins/pjx_chip_input/test_pjx_chip_input_build_chip.py:20` | `browser/builtins/test_pjx_chip_input.py` | `Path(__file__).resolve().parents[4]` | `Path(__file__).resolve().parents[3]` |
| `pyjinhx/builtins/pjx_confirm_dialog/test_pjx_confirm_dialog_theme.py:16` | `browser/builtins/test_pjx_confirm_dialog.py` | `Path(__file__).resolve().parents[4]` | `Path(__file__).resolve().parents[3]` |
| `pyjinhx/builtins/pjx_drawer/test_pjx_drawer_layer.py:14` | `browser/builtins/test_pjx_drawer.py` | `Path(__file__).resolve().parents[4]` | `Path(__file__).resolve().parents[3]` |
| `pyjinhx/builtins/pjx_dropdown/test_pjx_dropdown_layer.py:16` | `browser/builtins/test_pjx_dropdown.py` | `Path(__file__).resolve().parents[4]` | `Path(__file__).resolve().parents[3]` |
| `pyjinhx/builtins/pjx_modal/test_pjx_modal_theme.py:16` | `browser/builtins/test_pjx_modal.py` | `Path(__file__).resolve().parents[4]` | `Path(__file__).resolve().parents[3]` |
| `pyjinhx/builtins/pjx_popover/test_pjx_popover_assets.py:14` | `unit/builtins/test_pjx_popover.py` | `Path(__file__).resolve().parents[4]` | `Path(__file__).resolve().parents[3]` |
| `pyjinhx/builtins/pjx_prompt_dialog/test_pjx_prompt_dialog_theme.py:16` | `browser/builtins/test_pjx_prompt_dialog.py` | `Path(__file__).resolve().parents[4]` | `Path(__file__).resolve().parents[3]` |
| `pyjinhx/builtins/test_feedback_theme_tokens.py:12` | `unit/builtins/theme_tokens/test_feedback.py` | `Path(__file__).parents[3]` | `Path(__file__).parents[4]` |
| `pyjinhx/builtins/test_navigation_theme_tokens.py:12` | `unit/builtins/theme_tokens/test_navigation.py` | `Path(__file__).parents[3]` | `Path(__file__).parents[4]` |
| `pyjinhx/integrations/test_fastapi_wiring.py:31` | `unit/integrations/fastapi/test_wiring.py` | `Path(__file__).parent.parent.parent` | `Path(__file__).parents[3]` |
| `pyjinhx/integrations/test_reactive_request_cycle.py:107` | `unit/integrations/fastapi/test_request_cycle.py` | `Path(__file__).parent.parent.parent / "templates"` | `Path(__file__).parents[3] / "fixtures" / "templates"` |
| `pyjinhx/integrations/test_reactive_request_cycle.py:123` | `unit/integrations/fastapi/test_request_cycle.py` | `Path(__file__).parent.parent.parent / "templates"` | `Path(__file__).parents[3] / "fixtures" / "templates"` |
| `pyjinhx/reactive/test_reactive_mount.py:28` | `unit/reactive/component/test_mount.py` | `Path(__file__).parent.parent.parent / "templates"` | `Path(__file__).parents[3] / "fixtures" / "templates"` |
| `pyjinhx/reactive/test_reactive_root_attrs.py:27` | `unit/reactive/test_root_attrs.py` | `Path(__file__).parent.parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_asset_emission.py:8` | `unit/assets/test_emission.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_asset_emission.py:205` | `unit/assets/test_emission.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_assets.py:17` | `unit/assets/test_accumulation.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_concurrency.py:45` | `unit/session/test_concurrency.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_direct_nesting.py:25` | `unit/slots/test_direct_nesting.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_discovery.py:13` | `unit/discovery/test_walk.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_discovery_matrix.py:21` | `unit/discovery/test_combined.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_instance_registry.py:31` | `unit/test_registry.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[1] / "fixtures" / "templates"` |
| `pyjinhx/test_registry.py:13` | `unit/discovery/test_registry.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_render_children.py:13` | `unit/rendering/test_children.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_render_cycle_guard.py:13` | `unit/rendering/test_cycle_guard.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_render_hook.py:18` | `unit/rendering/test_hook.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_render_integration.py:27` | `unit/rendering/test_integration.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_render_level.py:12` | `unit/rendering/test_level.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_render_nested_integration.py:20` | `unit/rendering/test_nested_integration.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_render_public.py:17` | `unit/rendering/test_public.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_render_public.py:209` | `unit/rendering/test_public.py` | `Path(__file__).parent.parent` | `Path(__file__).parents[2]` |
| `pyjinhx/test_render_splice.py:14` | `unit/rendering/test_splice.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_replace.py:13` | `unit/discovery/test_replace.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_session.py:24` | `unit/session/test_session.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_slot_collections.py:20` | `unit/slots/test_collections.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_slot_props_view.py:16` | `unit/slots/test_props_view.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_slot_semantics_matrix.py:25` | `unit/slots/test_semantics.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_slot_type_v2.py:21` | `unit/slots/test_slot_type.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_stale_header_warning.py:25` | `unit/rendering/test_stale_header_warning.py` | `Path(__file__).parent.parent / "templates"` | `Path(__file__).parents[2] / "fixtures" / "templates"` |
| `pyjinhx/test_theme_tokens.py:12` | `unit/builtins/theme_tokens/test_stylesheets.py` | `Path(__file__).parents[2]` | `Path(__file__).parents[4]` |
| `test_bench_scripts_smoke.py:22` | `scripts/test_bench.py` | `Path(__file__).parent.parent` | `Path(__file__).parents[2]` |
| `test_fold_script.py:22` | `scripts/test_fold_components.py` | `Path(__file__).parent.parent` | `Path(__file__).parents[2]` |
| `test_package_layout.py:17` | `packaging/test_package_layout.py` | `Path(__file__).resolve().parent.parent` | `Path(__file__).resolve().parents[2]` |
| `test_theme_token_reference.py:15` | `docs/test_theme_token_reference.py` | `Path(__file__).resolve().parents[1]` | `Path(__file__).resolve().parents[2]` |
| `test_theming_guide.py:11` | `docs/test_theming_guide.py` | `Path(__file__).resolve().parents[1]` | `Path(__file__).resolve().parents[2]` |

Four more that the table does not show in full:

| File:line (old path) | Change |
|---|---|
| `tests/pyjinhx/builtins/pjx_graph/conftest.py:17` (`ASSET`) | Moves with `graph_page` to `tests/browser/builtins/pjx_graph/conftest.py`; still four folders deep, so `parents[4]` stays. |
| `tests/pyjinhx/integrations/test_fastapi_wiring.py:31-33` | The expression continues on the next line with `/ "templates"`, which becomes `/ "fixtures" / "templates"`; the table row above only shows the first line. |
| `tests/pyjinhx/test_session.py:213, 217` | `template_dir="tests/templates"` is a dummy argument to a call that must raise `TypeError`. Change to `"tests/fixtures/templates"` only so the old path no longer appears in a grep. |
| `tests/test_package_layout.py:109, 185` | The skip entry `"tests/test_package_layout.py"` becomes `"tests/packaging/test_package_layout.py"`. Without this the file fails its own two "no tracked file mentions..." tests. |

Expressions that mean "the folder this test file is in" follow the file and need no
edit: `test_component_descriptor.py` (ten uses of `Path(__file__).parent`),
`test_sfc_component.py` (`THIS_FILE`), `integrations/test_base.py:42, 180`,
`test_stale_header_warning.py:43`.

### 3.3 Template names

After the topic move, each template name passed to a helper that joins it onto the
templates folder gains its topic. Both quote styles occur (two f-strings use single
quotes: `test_render_cycle_guard.py:141`, `test_slot_semantics_matrix.py:189`).

| Old file | New file | Lines: literal -> topic-prefixed literal |
|---|---|---|
| `pyjinhx/integrations/test_fastapi_wiring.py` | `unit/integrations/fastapi/test_wiring.py` | `pjx_integrations_greeting.html` -> `fastapi/pjx_integrations_greeting.html` (L33) |
| `pyjinhx/integrations/test_reactive_request_cycle.py` | `unit/integrations/fastapi/test_request_cycle.py` | `cycle_badge.css` -> `fastapi/cycle_badge.css` (L135, 351, 362, 407); `cycle_badge.js` -> `fastapi/cycle_badge.js` (L136, 352, 363); `cycle_badge.pjx` -> `fastapi/cycle_badge.pjx` (L134); `cycle_card.pjx` -> `fastapi/cycle_card.pjx` (L130); `cycle_nested.pjx` -> `fastapi/cycle_nested.pjx` (L139); `cycle_shell.pjx` -> `fastapi/cycle_shell.pjx` (L142) |
| `pyjinhx/reactive/test_reactive_mount.py` | `unit/reactive/component/test_mount.py` | `container_only_plain.html` -> `reactive/container_only_plain.html` (L171); `plain_widget.html` -> `reactive/plain_widget.html` (L60); `reactive_keyed_json_attr.html` -> `reactive/reactive_keyed_json_attr.html` (L125); `reactive_keyed_list_widget.html` -> `reactive/reactive_keyed_list_widget.html` (L116); `reactive_keyed_override.html` -> `reactive/reactive_keyed_override.html` (L101); `reactive_keyed_twice.html` -> `reactive/reactive_keyed_twice.html` (L92); `reactive_keyed_widget.html` -> `reactive/reactive_keyed_widget.html` (L83); `reactive_mount_container.html` -> `reactive/reactive_mount_container.html` (L68); `reactive_widget.html` -> `reactive/reactive_widget.html` (L58) |
| `pyjinhx/reactive/test_reactive_root_attrs.py` | `unit/reactive/test_root_attrs.py` | `inner_badge.html` -> `reactive/inner_badge.html` (L153); `middle_wrap.html` -> `reactive/middle_wrap.html` (L154); `plain_widget.html` -> `reactive/plain_widget.html` (L53); `reactive_attrs.html` -> `reactive/reactive_attrs.html` (L80); `reactive_builtin_root.html` -> `reactive/reactive_builtin_root.html` (L156); `reactive_double_root.html` -> `reactive/reactive_double_root.html` (L159); `reactive_inner_root.html` -> `reactive/reactive_inner_root.html` (L181); `reactive_nested_reactive_root.html` -> `reactive/reactive_nested_reactive_root.html` (L184); `reactive_prestamped.html` -> `reactive/reactive_prestamped.html` (L78); `reactive_prologue_root.html` -> `reactive/reactive_prologue_root.html` (L168); `reactive_shell.html` -> `reactive/reactive_shell.html` (L85, 118, 127); `reactive_void.html` -> `reactive/reactive_void.html` (L76); `reactive_widget.html` -> `reactive/reactive_widget.html` (L51, 82, 112, 115) |
| `pyjinhx/test_asset_emission.py` | `unit/assets/test_emission.py` | `nested_emit_parent.html` -> `nesting/nested_emit_parent.html` (L562); `plain_div.html` -> `basic/plain_div.html` (L211) |
| `pyjinhx/test_assets.py` | `unit/assets/test_accumulation.py` | `plain_div.html` -> `basic/plain_div.html` (L31) |
| `pyjinhx/test_concurrency.py` | `unit/session/test_concurrency.py` | `div.html` -> `basic/div.html` (L111, 120) |
| `pyjinhx/test_direct_nesting.py` | `unit/slots/test_direct_nesting.py` | `nest_attr.html` -> `nesting/nest_attr.html` (L273); `nest_content.html` -> `nesting/nest_content.html` (L58, 86, 99, 174, 196, 225, 241, 260); `nest_if.html` -> `nesting/nest_if.html` (L141, 155); `nest_leaf.html` -> `nesting/nest_leaf.html` (L49, 80); `nest_wrap.html` -> `nesting/nest_wrap.html` (L115, 127, 167, 189) |
| `pyjinhx/test_instance_registry.py` | `unit/test_registry.py` | `reactive_widget.html` -> `reactive/reactive_widget.html` (L220, 328) |
| `pyjinhx/test_render_children.py` | `unit/rendering/test_children.py` | `unknown_host.html` -> `basic/unknown_host.html` (L121) |
| `pyjinhx/test_render_cycle_guard.py` | `unit/rendering/test_cycle_guard.py` | `cycle_a.html` -> `cycle/cycle_a.html` (L83, 141); `cycle_acyclic_a.html` -> `cycle/cycle_acyclic_a.html` (L88); `cycle_acyclic_b.html` -> `cycle/cycle_acyclic_b.html` (L89); `cycle_acyclic_c.html` -> `cycle/cycle_acyclic_c.html` (L90); `cycle_b.html` -> `cycle/cycle_b.html` (L84); `cycle_card_l2.html` -> `cycle/cycle_card_l2.html` (L93); `cycle_diamond.html` -> `cycle/cycle_diamond.html` (L91); `cycle_long_a.html` -> `cycle/cycle_long_a.html` (L85); `cycle_long_b.html` -> `cycle/cycle_long_b.html` (L86); `cycle_long_c.html` -> `cycle/cycle_long_c.html` (L87); `cycle_passthrough.html` -> `cycle/cycle_passthrough.html` (L92); `cycle_row_l2.html` -> `cycle/cycle_row_l2.html` (L94); `cycle_self.html` -> `cycle/cycle_self.html` (L82) |
| `pyjinhx/test_render_hook.py` | `unit/rendering/test_hook.py` | `nested_leaf.html` -> `nesting/nested_leaf.html` (L38); `nested_mid.html` -> `nesting/nested_mid.html` (L45); `nested_root.html` -> `nesting/nested_root.html` (L52) |
| `pyjinhx/test_render_integration.py` | `unit/rendering/test_integration.py` | `integration_attrs.html` -> `integration/integration_attrs.html` (L134); `integration_childless.html` -> `integration/integration_childless.html` (L38); `integration_escape.html` -> `integration/integration_escape.html` (L68); `integration_full.html` -> `integration/integration_full.html` (L173); `integration_slot.html` -> `integration/integration_slot.html` (L104) |
| `pyjinhx/test_render_level.py` | `unit/rendering/test_level.py` | `bad.html` -> `basic/bad.html` (L174, 666); `broken_assertion.html` -> `basic/broken_assertion.html` (L725); `card.html` -> `basic/card.html` (L292); `child_button.html` -> `basic/child_button.html` (L43); `child_card.html` -> `basic/child_card.html` (L45); `child_icon.html` -> `basic/child_icon.html` (L47); `container.html` -> `basic/container.html` (L110); `div.html` -> `basic/div.html` (L76, 696); `empty.html` -> `basic/empty.html` (L199, 636); `icon.html` -> `basic/icon.html` (L259); `lowercase.html` -> `basic/lowercase.html` (L356); `minimal.html` -> `basic/minimal.html` (L499, 539); `mixedcase.html` -> `basic/mixedcase.html` (L388); `nested.html` -> `basic/nested.html` (L140); `roundtrip.html` -> `basic/roundtrip.html` (L449); `slot_interp.html` -> `slots/slot_interp.html` (L769); `slot_leaf.html` -> `slots/slot_leaf.html` (L760); `slotted.html` -> `slots/slotted.html` (L421); `test.html` -> `basic/test.html` (L226); `unsafe.html` -> `basic/unsafe.html` (L328) |
| `pyjinhx/test_render_nested_integration.py` | `unit/rendering/test_nested_integration.py` | `nested_bad_leaf.html` -> `nesting/nested_bad_leaf.html` (L273); `nested_bad_mid.html` -> `nesting/nested_bad_mid.html` (L280); `nested_bad_root.html` -> `nesting/nested_bad_root.html` (L287); `nested_branches.html` -> `nesting/nested_branches.html` (L108); `nested_full_mid.html` -> `nesting/nested_full_mid.html` (L223); `nested_full_root.html` -> `nesting/nested_full_root.html` (L230); `nested_leaf.html` -> `nesting/nested_leaf.html` (L40); `nested_loop.html` -> `nesting/nested_loop.html` (L184); `nested_mid.html` -> `nesting/nested_mid.html` (L47); `nested_mixed_mid.html` -> `nesting/nested_mixed_mid.html` (L140); `nested_mixed_root.html` -> `nesting/nested_mixed_root.html` (L147); `nested_root.html` -> `nesting/nested_root.html` (L54) |
| `pyjinhx/test_render_public.py` | `unit/rendering/test_public.py` | `bad.html` -> `basic/bad.html` (L161); `div.html` -> `basic/div.html` (L42, 182, 191, 210); `empty.html` -> `basic/empty.html` (L171); `roundtrip.html` -> `basic/roundtrip.html` (L59) |
| `pyjinhx/test_render_splice.py` | `unit/rendering/test_splice.py` | `splice_bad_child.html` -> `splice/splice_bad_child.html` (L131); `splice_bad_parent.html` -> `splice/splice_bad_parent.html` (L138); `splice_child.html` -> `splice/splice_child.html` (L34); `splice_mixed.html` -> `splice/splice_mixed.html` (L99); `splice_parent.html` -> `splice/splice_parent.html` (L41); `splice_plain.html` -> `splice/splice_plain.html` (L48); `splice_siblings.html` -> `splice/splice_siblings.html` (L92) |
| `pyjinhx/test_session.py` | `unit/session/test_session.py` | `plain_div.html` -> `basic/plain_div.html` (L232, 872) |
| `pyjinhx/test_slot_collections.py` | `unit/slots/test_collections.py` | `nest_wrap.html` -> `nesting/nest_wrap.html` (L344); `slot_dict.html` -> `slots/slot_dict.html` (L162, 204, 365, 384, 395, 403, 447); `slot_if.html` -> `slots/slot_if.html` (L479, 487, 495, 505); `slot_interp.html` -> `slots/slot_interp.html` (L214, 226); `slot_leaf.html` -> `slots/slot_leaf.html` (L44); `slot_list.html` -> `slots/slot_list.html` (L145, 179, 187, 194, 236, 251, 265, 276, 287, 307, 328, 350, 464); `slot_list_len.html` -> `slots/slot_list_len.html` (L420, 433) |
| `pyjinhx/test_slot_props_view.py` | `unit/slots/test_props_view.py` | `nest_content.html` -> `nesting/nest_content.html` (L487); `nest_wrap.html` -> `nesting/nest_wrap.html` (L428); `slot_if.html` -> `slots/slot_if.html` (L374, 381); `slot_interp.html` -> `slots/slot_interp.html` (L363); `slot_leaf.html` -> `slots/slot_leaf.html` (L37, 481); `slot_props.html` -> `slots/slot_props.html` (L278, 289, 298, 319, 330, 411, 430); `slot_props_bare_view.html` -> `slots/slot_props_bare_view.html` (L339); `slot_props_dict.html` -> `slots/slot_props_dict.html` (L399); `slot_props_list.html` -> `slots/slot_props_list.html` (L388) |
| `pyjinhx/test_slot_semantics_matrix.py` | `unit/slots/test_semantics.py` | `nest_content.html` -> `nesting/nest_content.html` (L71, 156, 189, 529, 536, 591, 645); `nest_if.html` -> `nesting/nest_if.html` (L89, 103, 110); `nest_leaf.html` -> `nesting/nest_leaf.html` (L49); `slot_dict.html` -> `slots/slot_dict.html` (L362, 383, 399); `slot_header_content.html` -> `slots/slot_header_content.html` (L285); `slot_leaf.html` -> `slots/slot_leaf.html` (L340); `slot_list.html` -> `slots/slot_list.html` (L352, 377, 408); `slot_list_len.html` -> `slots/slot_list_len.html` (L393); `slot_mixed_kinds.html` -> `slots/slot_mixed_kinds.html` (L120, 129, 143); `slot_props.html` -> `slots/slot_props.html` (L455, 472, 480, 504); `slot_props_dict.html` -> `slots/slot_props_dict.html` (L428); `slot_props_list.html` -> `slots/slot_props_list.html` (L421, 435) |
| `pyjinhx/test_slot_type_v2.py` | `unit/slots/test_slot_type.py` | `div.html` -> `basic/div.html` (L224); `nest_content.html` -> `nesting/nest_content.html` (L577, 592); `slot_if.html` -> `slots/slot_if.html` (L225, 237); `slot_interp.html` -> `slots/slot_interp.html` (L271, 289, 311, 371); `slot_leaf.html` -> `slots/slot_leaf.html` (L270, 310) |
| `pyjinhx/test_stale_header_warning.py` | `unit/rendering/test_stale_header_warning.py` | `stale_render.html` -> `basic/stale_render.html` (L78, 147) |

Left alone on purpose:

- `pyjinhx/test_render_cache_wiring.py:403` — `icon = tmp_path / "icon.html"`
- `pyjinhx/test_render_level.py:654` — `assert "empty.html" in message`
- `pyjinhx/test_render_level.py:684` — `assert "bad.html" in message`
- `pyjinhx/test_render_nested_integration.py:298` — `assert "nested_bad_leaf.html" in message`
- `pyjinhx/test_render_splice.py:159` — `assert "splice_bad_child.html" in str(excinfo.value)`
- `pyjinhx/test_slot_collections.py:441` — `assert "slot_list_len.html" in message`
- `pyjinhx/test_slot_props_view.py:120` — `owner_template=Path("slot_props.html"),`
- `pyjinhx/test_slot_semantics_matrix.py:513` — `owner_template=Path("slot_props.html"),`
- `pyjinhx/test_slot_semantics_matrix.py:577` — `owner_template=Path("slot_props.html"),`
- `pyjinhx/test_slot_type_v2.py:432` — `template_path=Path("slot_leaf.html"),`

The four `Path("...")` cases are bare relative paths used as labels, not files on disk.
The `assert "x.html" in message` cases stay true either way, since the message holds
the full path.

`test_reactive_request_cycle.py` passes the templates folder to `discovery.build_registry`
(line 123). Keep that pointed at `tests/fixtures/templates` itself, not at `fastapi/`:
the walk is recursive, so it then finds exactly the `.pjx` files it finds today (the
four `cycle_*.pjx` plus the ones under `discovery/`), and the orphan set does not change.

### 3.4 Old test paths written in prose, CI and docs

| File:line | Old reference | New reference |
|---|---|---|
| `.claude/skills/dead-code-audit/SKILL.md:93` | `tests/test_package_layout.py` | `tests/packaging/test_package_layout.py` |
| `.claude/skills/dead-code-audit/SKILL.md:131` | `tests/test_package_layout.py` | `tests/packaging/test_package_layout.py` |
| `.claude/skills/public-api-audit/SKILL.md:5` | `tests/test_package_layout.py` | `tests/packaging/test_package_layout.py` |
| `.claude/skills/public-api-audit/SKILL.md:37` | `tests/test_package_layout.py` | `tests/packaging/test_package_layout.py` |
| `.github/workflows/docs-check.yml:35` | `tests/pyjinhx/test_docs_reference_real_fields.py` | `tests/docs/test_reference_real_fields.py` |
| `.github/workflows/tests.yml:31` | `tests/pyjinhx` | `replaced, see 5.3` |
| `.github/workflows/tests.yml:70` | `tests/minimal` | `tests/packaging/test_minimal_install.py` |
| `docs/decisions/0005-roster-picker.md:39` | `tests/pyjinhx/builtins/pjx_popover/test_pjx_popover_assets.py` | `tests/unit/builtins/test_pjx_popover.py` |
| `docs/decisions/0005-roster-picker.md:47` | `tests/pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_js_build.py` | `tests/unit/builtins/pjx_roster_picker/test_js_build.py` |
| `docs/guide/builtin-conventions.md:42` | `tests/pyjinhx/test_slot_type_v2.py` | `tests/unit/slots/test_slot_type.py` |
| `pyjinhx/_component.py:10` | `tests/pyjinhx/test_import_graph.py` | `tests/packaging/test_import_graph.py` |
| `pyjinhx/builtins/ui/pjx_popover/pjx_popover.js:98` | `tests/.../test_pjx_popover_assets.py` | `tests/unit/builtins/test_pjx_popover.py` |
| `pyjinhx/builtins/ui/pjx_select/pjx_select.js:98` | `tests/.../test_pjx_select_assets.py` | `tests/unit/builtins/pjx_select/test_assets.py` |
| `pyjinhx/markers.py:93` | `tests/pyjinhx/test_slot_type_v2.py` | `tests/unit/slots/test_slot_type.py` |
| `pyjinhx/markers.py:93` | `tests/pyjinhx` | `tests/unit/test_render_context.py (the path continues on the next line)` |
| `pyjinhx/rendering.py:257` | `tests/pyjinhx/test_assets.py` | `tests/unit/assets/test_accumulation.py` |
| `scripts/bench_field_count.py:45` | `tests/test_bench_scripts_smoke.py` | `tests/scripts/test_bench.py` |
| `scripts/bench_mixed_reactive_tree.py:41` | `tests/test_bench_scripts_smoke.py` | `tests/scripts/test_bench.py` |
| `scripts/bench_parser_tagfree.py:43` | `tests/test_bench_scripts_smoke.py` | `tests/scripts/test_bench.py` |
| `scripts/bench_reactive_cache.py:29` | `tests/test_bench_scripts_smoke.py` | `tests/scripts/test_bench.py` |
| `scripts/bench_reactive_fanout.py:67` | `tests/test_bench_scripts_smoke.py` | `tests/scripts/test_bench.py` |
| `scripts/bench_render_depth.py:37` | `tests/test_bench_scripts_smoke.py` | `tests/scripts/test_bench.py` |
| `scripts/bench_render_scaling.py:29` | `tests/test_bench_scripts_smoke.py` | `tests/scripts/test_bench.py` |
| `scripts/bench_render_scaling_v2.py:35` | `tests/test_bench_scripts_smoke.py` | `tests/scripts/test_bench.py` |
| `scripts/bench_slot_payload.py:51` | `tests/test_bench_scripts_smoke.py` | `tests/scripts/test_bench.py` |
| `scripts/bench_state_hash.py:34` | `tests/test_bench_scripts_smoke.py` | `tests/scripts/test_bench.py` |
| `tests/pyjinhx/builtins/pjx_alert/test_pjx_alert.py:22` | `tests/pyjinhx/builtins/pjx_notification` | `tests/unit/builtins/test_pjx_notification.py` |
| `tests/pyjinhx/builtins/pjx_avatar/test_pjx_avatar.py:17` | `tests/pyjinhx/builtins/pjx_badge` | `tests/unit/builtins/test_pjx_badge.py` |
| `tests/pyjinhx/builtins/pjx_avatar_stack/test_pjx_avatar_stack.py:15` | `tests/pyjinhx/builtins/pjx_badge` | `tests/unit/builtins/test_pjx_badge.py` |
| `tests/pyjinhx/builtins/pjx_badge/test_pjx_badge.py:19` | `tests/pyjinhx/builtins/pjx_icon` | `tests/unit/builtins/test_pjx_icon.py` |
| `tests/pyjinhx/builtins/pjx_badge/test_pjx_badge.py:107` | `tests/pyjinhx/builtins/pjx_avatar/test_pjx_avatar.py` | `tests/unit/builtins/test_pjx_avatar.py` |
| `tests/pyjinhx/builtins/pjx_card/test_pjx_card.py:77` | `tests/pyjinhx/test_slot_collections.py` | `tests/unit/slots/test_collections.py` |
| `tests/pyjinhx/builtins/pjx_card/test_pjx_card.py:80` | `tests/pyjinhx/builtins/test_family_display_primitives_sweep.py` | `tests/unit/builtins/families/test_display_primitives.py` |
| `tests/pyjinhx/builtins/pjx_card_body/test_pjx_card_body.py:17` | `tests/pyjinhx/builtins/pjx_empty_state` | `tests/unit/builtins/test_pjx_empty_state.py` |
| `tests/pyjinhx/builtins/pjx_chart/conftest.py:17` | `tests/pyjinhx/client/conftest.py` | `tests/browser/conftest.py` |
| `tests/pyjinhx/builtins/pjx_divider/test_pjx_divider.py:17` | `tests/pyjinhx/builtins/pjx_badge` | `tests/unit/builtins/test_pjx_badge.py` |
| `tests/pyjinhx/builtins/pjx_drawer/test_pjx_drawer.py:152` | `tests/pyjinhx/builtins/pjx_modal/test_pjx_modal.py` | `tests/unit/builtins/test_pjx_modal.py` |
| `tests/pyjinhx/builtins/pjx_empty_state/test_pjx_empty_state.py:18` | `tests/pyjinhx/builtins/pjx_divider` | `tests/unit/builtins/test_pjx_divider.py` |
| `tests/pyjinhx/builtins/pjx_graph/conftest.py:86` | `tests/pyjinhx/client/conftest.py` | `tests/browser/conftest.py` |
| `tests/pyjinhx/builtins/pjx_graph/test_pjx_graph_d3_vendor.py:53` | `tests/pyjinhx/client/conftest.py` | `tests/browser/conftest.py` |
| `tests/pyjinhx/builtins/pjx_modal/test_pjx_modal.py:91` | `tests/pyjinhx/builtins/pjx_card/test_pjx_card.py` | `tests/unit/builtins/test_pjx_card.py` |
| `tests/pyjinhx/builtins/pjx_notification/test_pjx_notification.py:22` | `tests/pyjinhx/builtins/test_pjx_region_loader.py` | `tests/unit/builtins/test_pjx_region_loader.py` |
| `tests/pyjinhx/builtins/pjx_popover/test_pjx_popover_portal.py:3` | `tests/pyjinhx/builtins/pjx_tooltip` | `tests/browser/builtins/pjx_tooltip` |
| `tests/pyjinhx/builtins/pjx_popover/test_pjx_popover_position.py:32` | `tests/pyjinhx/client/conftest.py` | `tests/browser/conftest.py` |
| `tests/pyjinhx/builtins/pjx_progress/test_pjx_progress.py:17` | `tests/pyjinhx/builtins/pjx_divider` | `tests/unit/builtins/test_pjx_divider.py` |
| `tests/pyjinhx/builtins/pjx_roster_picker/conftest.py:107` | `tests/pyjinhx/client/conftest.py` | `tests/browser/conftest.py` |
| `tests/pyjinhx/builtins/pjx_skeleton/test_pjx_skeleton.py:17` | `tests/pyjinhx/builtins/pjx_divider` | `tests/unit/builtins/test_pjx_divider.py` |
| `tests/pyjinhx/builtins/pjx_spinner/test_pjx_spinner.py:17` | `tests/pyjinhx/builtins/pjx_progress` | `tests/unit/builtins/test_pjx_progress.py` |
| `tests/pyjinhx/builtins/pjx_toggle_switch/test_pjx_toggle_switch.py:5` | `tests/pyjinhx/builtins/pjx_segmented_control` | `tests/unit/builtins/test_pjx_segmented_control.py` |
| `tests/pyjinhx/builtins/test_family_data_htmx_sweep.py:74` | `tests/pyjinhx/test_render_context.py` | `tests/unit/test_render_context.py` |
| `tests/pyjinhx/builtins/test_family_data_htmx_sweep.py:79` | `tests/pyjinhx/test_direct_nesting.py` | `tests/unit/slots/test_direct_nesting.py` |
| `tests/pyjinhx/builtins/test_family_js_heavy_sweep.py:4` | `tests/pyjinhx/builtins/pjx_` | `tests/unit/builtins/` |
| `tests/pyjinhx/builtins/test_family_js_heavy_sweep.py:15` | `tests/pyjinhx/client/test_pjx_toast.py` | `tests/browser/client/test_toast.py` |
| `tests/pyjinhx/builtins/test_family_js_heavy_sweep.py:420` | `tests/pyjinhx/client/test_pjx_toast.py` | `tests/browser/client/test_toast.py` |
| `tests/pyjinhx/builtins/test_feedback_theme_tokens.py:16` | `tests/pyjinhx/test_theme_tokens.py` | `tests/unit/builtins/theme_tokens/test_stylesheets.py` |
| `tests/pyjinhx/builtins/test_navigation_theme_tokens.py:15` | `tests/pyjinhx/builtins/test_feedback_theme_tokens.py` | `tests/unit/builtins/theme_tokens/test_feedback.py` |
| `tests/pyjinhx/builtins/test_pjx_lazy_load.py:153` | `tests/pyjinhx/test_asset_emission.py` | `tests/unit/assets/test_emission.py` |
| `tests/pyjinhx/client/test_page_loader_namespace.py:26` | `tests/pyjinhx/builtins/test_pjx_page_loader.py` | `tests/unit/builtins/test_pjx_page_loader.py` |
| `tests/pyjinhx/integrations/test_reactive_request_cycle.py:48` | `tests/pyjinhx/reactive/test_reactive_mutations.py` | `tests/unit/reactive/test_mutations.py` |
| `tests/pyjinhx/reactive/test_fanout_assets.py:206` | `tests/pyjinhx/test_session.py` | `tests/unit/session/test_session.py` |
| `tests/pyjinhx/reactive/test_fanout_assets.py:332` | `tests/pyjinhx/test_session.py` | `tests/unit/session/test_session.py` |
| `tests/pyjinhx/reactive/test_reactive_fanout.py:358` | `tests/pyjinhx/test_render_integration.py` | `tests/unit/rendering/test_integration.py` |
| `tests/pyjinhx/test_component.py:571` | `tests/pyjinhx/test_import_graph.py` | `tests/packaging/test_import_graph.py` |
| `tests/pyjinhx/test_direct_nesting.py:29` | `tests/templates` | `tests/fixtures/templates` |
| `tests/pyjinhx/test_gallery_demos.py:34` | `tests/pyjinhx/client/test_pjx_theme_inject.py` | `tests/browser/client/test_theme.py / tests/unit/client/test_inject.py` |
| `tests/pyjinhx/test_gallery_demos.py:361` | `tests/pyjinhx/test_theme_tokens.py` | `tests/unit/builtins/theme_tokens/test_stylesheets.py` |
| `tests/pyjinhx/test_gallery_theme_toggle_browser.py:40` | `tests/pyjinhx/builtins/pjx_chart/conftest.py` | `tests/browser/conftest.py` |
| `tests/pyjinhx/test_instance_registry.py:403` | `tests/pyjinhx/test_session.py` | `tests/unit/session/test_session.py` |
| `tests/pyjinhx/test_render_cache_behavior.py:197` | `tests/pyjinhx/test_assets.py` | `tests/unit/assets/test_accumulation.py` |
| `tests/pyjinhx/test_render_cache_wiring.py:328` | `tests/pyjinhx/test_assets.py` | `tests/unit/assets/test_accumulation.py` |
| `tests/pyjinhx/test_render_public.py:21` | `tests/templates` | `tests/fixtures/templates` |
| `tests/pyjinhx/test_session.py:213` | `tests/templates` | `tests/fixtures/templates` |
| `tests/pyjinhx/test_session.py:217` | `tests/templates` | `tests/fixtures/templates` |
| `tests/pyjinhx/test_slot_collections.py:24` | `tests/templates` | `tests/fixtures/templates` |
| `tests/pyjinhx/test_slot_props_view.py:20` | `tests/templates` | `tests/fixtures/templates` |
| `tests/pyjinhx/test_slot_semantics_matrix.py:29` | `tests/templates` | `tests/fixtures/templates` |
| `tests/pyjinhx/test_stale_header_warning.py:75` | `tests/templates` | `tests/fixtures/templates` |
| `tests/pyjinhx/test_theme_tokens.py:15` | `tests/pyjinhx/client/test_pjx_theme.py` | `tests/unit/client/test_client.py` |
| `tests/test_package_layout.py:109` | `tests/test_package_layout.py` | `tests/packaging/test_package_layout.py` |
| `tests/test_package_layout.py:185` | `tests/test_package_layout.py` | `tests/packaging/test_package_layout.py` |

Notes on that table:

- `pjx_popover.js:98` and `pjx_select.js:98` each name the other builtin's asset test.
  Those two `.js` files share a block that the tests they mention compare byte for
  byte; edit both comments the same way and rerun
  `tests/unit/builtins/test_pjx_popover.py` and `tests/unit/builtins/pjx_select/test_assets.py`.
- Comments that say "mirroring tests/pyjinhx/client/conftest.py" sit on copies of the
  chromium guard; the guard's home is now `tests/browser/conftest.py`.
- `tests.yml:31` and `:34` are replaced, not renamed (section 5.3).
- References to `tests/unit/...` and `tests/reactivity/...` in docstrings are history
  ("ported from v0.x tests/unit/test_button.py") and are not in the table. They now
  collide with a real folder name, so reword each to "the v0.x suite's
  `test_button.py`" while touching the file. `git grep -n 'v0.x tests/' -- tests` lists them.
- `CHANGELOG.md` and `docs/superpowers/` are history and stay as written.

## 4. Conftest restructuring

### 4.1 `tests/conftest.py`

`tests/pyjinhx/conftest.py` moves here unchanged (`git mv`), then gains the `session`
fixture and the marker hook.

| Fixture | Today | After | Same tests? |
|---|---|---|---|
| `render_cost_decisions`, `load_cost_decisions`, `no_orphan_templates`, `cache_everything_by_default` (all autouse, function scope) | `tests/pyjinhx/**`: 6060 tests | `tests/**`: 6296 tests | No: 236 more (below) |
| `render_session`, `write` (and the `Write` alias) | `tests/pyjinhx/**` | `tests/**` | Yes; only requested by name |
| `session` (plain `RenderSession()`) | defined twice, in the graph and roster picker conftests | once, here | Yes (below) |

The four autouse fixtures cannot keep their exact reach. Their old boundary was "under
`tests/pyjinhx/`", and that folder's tests now land in every new top-level folder next
to tests that were outside it (for example `packaging/` gets `test_import_graph.py`
from inside and `test_package_layout.py` from outside). The 236 newly covered tests are
`tests/examples/` (72), `tests/minimal/` (3) and the seven `tests/test_*.py` files (161).

Why that is safe: each fixture only resets process-wide state to its starting value, or
sets `PJX_RENDER_CACHE_MIN_US=0` for the test. It was also run: the whole suite with
the four fixtures registered globally (every one of the 6296 tests requesting them)
gave the baseline result exactly, `6291 passed, 1 skipped, 3 xfailed, 1 xpassed`.
The CI minimal-install leg will now import this conftest with no extras installed; its
imports (`pyjinhx.discovery`, `pyjinhx.reactive.load_cost`, `pyjinhx.render_cache`,
`pyjinhx.session`) were checked to load with fastapi, starlette, diskcache, redis, httpx
and playwright all blocked.

`session`: 39 test modules and `tests/examples/conftest.py` define their own `session`,
and a closer definition always wins, so those tests keep the fixture they have. The root
one only serves the graph and roster picker tests, which get the same `RenderSession()`
as before from one place instead of four (two unit folders, two browser folders).

### 4.2 Per-folder conftests

| New conftest | Contents | From |
|---|---|---|
| `tests/browser/conftest.py` | `_require_chromium` (autouse), `page_errors`, `console_errors` | the four copies in `client/`, `pjx_chart/`, `pjx_graph/`, `pjx_roster_picker/` conftests |
| `tests/browser/client/conftest.py` | `pjx_page`, `pjx_full_page` | `tests/pyjinhx/client/conftest.py` (`git mv`, then delete its `_require_chromium`) |
| `tests/browser/builtins/pjx_graph/conftest.py` | `ASSET`, `graph_page` | `pjx_graph/conftest.py` |
| `tests/unit/builtins/pjx_graph/conftest.py` | `El`, `_TreeBuilder`, `parse_html` | `pjx_graph/conftest.py` (`git mv`, then cut the browser fixtures and `session`) |
| `tests/unit/builtins/pjx_roster_picker/conftest.py` | `VOID_ELEMENTS`, `El`, `_TreeBuilder`, `parse_html` | `pjx_roster_picker/conftest.py` (`git mv`, then cut the same) |
| `tests/apps/todo/conftest.py` | `fresh_store` (autouse), `ctx`, `session`, `scope`, and one new autouse fixture, `todo_registry` (7.1) | `tests/examples/conftest.py`; still covers exactly the todo tests |

`tests/pyjinhx/builtins/pjx_chart/conftest.py` is deleted: both of its fixtures are in
`tests/browser/conftest.py`.

The two `parse_html` fixtures must not be unified. The roster picker one treats void
elements such as `<input>` as childless and records text; the graph one does neither,
so the same markup parses into different trees. Only non-browser tests use `parse_html`
(72 graph, 76 roster picker), which is why it lives under `unit/` only.

`_require_chromium` in `tests/browser/conftest.py` uses the `client/` conftest's body
(skip when the test asks for `page`, `pjx_page` or `pjx_full_page` and chromium is not
installed). The other three copies test `page` only, which is equivalent because
`pjx_page` and `pjx_full_page` depend on `page`. Who it applies to:

- Before: every test in the four folders, 950 of the 971 browser tests among them, plus
  22 test modules that carry their own copy.
- After: every test under `tests/browser/`, which is all 971 browser tests and nothing else.
- The difference is 21 tests in nine mixed files (button, carousel, chip_input,
  form_field, password_input, segmented_control, select, stack, toggle_switch) that have
  no guard today. With chromium installed nothing changes. Without it they now skip
  cleanly where today they error. Apart from the `todo_registry` fixture in 7.1, that
  is the only deliberate change to how any test behaves.
- The 22 module-level copies stay as they are; a module's own fixture overrides the
  conftest one and does the same thing. Removing them is a follow-up.
- Non-browser tests that used to sit under those four conftests ran the guard as a
  no-op (it returns at once unless a page is requested), so losing it changes nothing.

`page_errors` is also defined in `test_gallery_theme_toggle_browser.py`; that copy stays
and overrides.

### 4.3 Splitting the fourteen mixed files

Each file keeps its non-browser tests under `unit/`; the browser tests below move to
`browser/` with the helpers only they use. A helper both halves need is copied (they are
constants and one-line readers). Imports are trimmed in both halves until `ruff check`
is clean.

**`pyjinhx/builtins/pjx_button/test_pjx_button.py`** -> `unit/builtins/test_pjx_button.py` keeps the rest; `browser/builtins/test_pjx_button.py` receives:

- `test_button_defaults_follow_radius_and_spacing_tokens` (L227-244)
- moves with them (used by nothing else): `BUTTON_CSS` (L218), `_button_style` (L221)

**`pyjinhx/builtins/pjx_carousel/test_pjx_carousel.py`** -> `unit/builtins/test_pjx_carousel.py` keeps the rest; `browser/builtins/test_pjx_carousel.py` receives:

- class `TestAssets` is split: methods `test_app_override_sets_the_whole_timing`, `test_track_does_not_animate_under_reduced_motion`, `test_track_transition_has_no_delay` move into a `TestAssets` class in the browser file; the other methods stay
- copied, because both halves use it: `session` (L22), `_html` (L44), `_carousel_css` (L226), `_track_timing` (L230)

**`pyjinhx/builtins/pjx_chip_input/test_pjx_chip_input.py`** -> `unit/builtins/test_pjx_chip_input.py` keeps the rest; `browser/builtins/test_pjx_chip_input.py` receives:

- `test_chip_input_defaults_use_light_fallbacks` (L167-183)
- `test_chip_input_follows_theme_in_dark_mode` (L186-199)
- moves with them (used by nothing else): `CHIP_CSS` (L148), `CHIP_MARKUP` (L150), `_chip_style` (L160)

**`pyjinhx/builtins/pjx_form_field/test_pjx_form_field.py`** -> `unit/builtins/test_pjx_form_field.py` keeps the rest; `browser/builtins/test_pjx_form_field.py` receives:

- `test_form_field_colors_use_light_fallbacks_and_flip_in_dark` (L186-204)
- moves with them (used by nothing else): `FORM_FIELD_CSS` (L168), `FORM_FIELD_MARKUP` (L171), `_color` (L180)

**`pyjinhx/builtins/pjx_graph/test_pjx_graph_d3_vendor.py`** -> `unit/builtins/pjx_graph/test_d3_vendor.py` keeps the rest; `browser/builtins/pjx_graph/test_d3_vendor.py` receives:

- `test_exposes_exactly_the_engine_surface` (L136-146)
- `test_does_not_define_global_d3` (L149-150)
- `test_zoom_identity_builds_transforms` (L153-157)
- `test_zoom_installs_on_an_element_and_reads_back_identity` (L160-169)
- `test_selection_has_transition_side_effect` (L172-178)
- `test_evaluating_twice_does_not_throw` (L181-183)
- `test_binding_stays_local_inside_a_function_wrapper` (L186-193)
- moves with them (used by nothing else): `d3_page` (L65)
- copied, because both halves use it: `SOURCE` (L19)

**`pyjinhx/builtins/pjx_graph/test_pjx_graph_js_build.py`** -> `unit/builtins/pjx_graph/test_js_build.py` keeps the rest; `browser/builtins/pjx_graph/test_js_build.py` receives:

- `test_asset_defines_pjx_graph_and_leaks_no_d3` (L131-135)
- `test_reloading_keeps_the_same_graph_namespace` (L138-142)
- `test_loading_keeps_an_existing_pjx_namespace` (L145-151)
- copied, because both halves use it: `ROOT` (L22), `GRAPH_DIR` (L23), `ASSET` (L27)

**`pyjinhx/builtins/pjx_password_input/test_pjx_password_input.py`** -> `unit/builtins/test_pjx_password_input.py` keeps the rest; `browser/builtins/test_pjx_password_input.py` receives:

- `test_password_input_defaults_use_light_fallbacks` (L157-171)
- `test_password_input_focus_ring_uses_light_fallback` (L174-181)
- `test_password_input_component_token_still_wins` (L184-191)
- moves with them (used by nothing else): `PASSWORD_CSS` (L137), `PASSWORD_MARKUP` (L141), `_password_style` (L150)

**`pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker.py`** -> `unit/builtins/pjx_roster_picker/test_pjx_roster_picker.py` keeps the rest; `browser/builtins/pjx_roster_picker/test_theme.py` receives:

- `test_roster_picker_defaults_use_light_fallbacks` (L822-839)
- `test_roster_picker_results_layer_follows_popover_token` (L842-867)
- `test_roster_picker_follows_dark_theme` (L870-881)
- `test_roster_picker_follows_os_dark_preference` (L884-888)
- `test_roster_picker_portalled_results_keep_their_layer` (L891-894)
- `test_roster_picker_reduced_motion_drops_transitions` (L897-901)
- moves with them (used by nothing else): `PICKER_MARKUP` (L779), `PORTALLED_MARKUP` (L798), `_picker_page` (L801), `_picker_style` (L809), `_root_token` (L816)
- copied, because both halves use it: `PACKAGE_DIR` (L18), `CSS_PATH` (L25)

**`pyjinhx/builtins/pjx_segmented_control/test_pjx_segmented_control.py`** -> `unit/builtins/test_pjx_segmented_control.py` keeps the rest; `browser/builtins/test_pjx_segmented_control.py` receives:

- `test_segmented_control_defaults_use_light_fallbacks` (L150-170)
- moves with them (used by nothing else): `SEGMENTED_CSS` (L138), `_segment_style` (L143)

**`pyjinhx/builtins/pjx_select/test_pjx_select.py`** -> `unit/builtins/pjx_select/test_select.py` keeps the rest; `browser/builtins/pjx_select/test_theme.py` receives:

- `test_select_defaults_use_light_fallbacks` (L304-316)
- `test_select_panel_layer_follows_popover_token` (L319-334)
- `test_select_checkbox_accent_follows_brand` (L337-347)
- `test_select_selected_option_stays_visible_in_dark_mode` (L350-362)
- moves with them (used by nothing else): `SELECT_CSS` (L271), `SELECT_MARKUP` (L273), `CHECKBOX_MARKUP` (L284), `_select_page` (L290), `_select_style` (L297)

**`pyjinhx/builtins/pjx_select/test_pjx_select_keyboard.py`** -> `unit/builtins/pjx_select/test_keyboard.py` keeps the rest; `browser/builtins/pjx_select/test_keyboard.py` receives:

- `TestArrowNavigationRealDom` (L242-270)
- `TestTypeAheadRealDom` (L273-293)
- `TestCommitRealDom` (L296-327)
- `TestFilterAutofocusRealDom` (L330-364)
- `TestEscapeRealDom` (L367-384)
- moves with them (used by nothing else): `STYLE` (L155), `SINGLE` (L162), `SINGLE_NO_FILTER` (L188), `MULTIPLE` (L193), `_load` (L232), `_active_value` (L238)
- copied, because both halves use it: `UI` (L20), `CONTROLLER` (L21)

**`pyjinhx/builtins/pjx_stack/test_pjx_stack.py`** -> `unit/builtins/test_pjx_stack.py` keeps the rest; `browser/builtins/test_pjx_stack.py` receives:

- `test_unthemed_stack_uses_the_literal_fallback_gap` (L214-225)
- `test_themed_stack_follows_the_spacing_token` (L237-256)
- moves with them (used by nothing else): `CHILD` (L20), `_style` (L180), `_render_with_assets` (L187), `themed` (L229)

**`pyjinhx/builtins/pjx_toggle_switch/test_pjx_toggle_switch.py`** -> `unit/builtins/test_pjx_toggle_switch.py` keeps the rest; `browser/builtins/test_pjx_toggle_switch.py` receives:

- `test_toggle_switch_defaults_use_light_fallbacks` (L161-173)
- `test_toggle_switch_on_state_follows_theme_in_dark_mode` (L176-187)
- `test_toggle_switch_component_token_still_wins` (L190-197)
- moves with them (used by nothing else): `TOGGLE_CSS` (L141), `_toggle_markup` (L144), `_background` (L155)

**`pyjinhx/client/test_pjx_theme_inject.py`** -> `unit/client/test_inject.py` keeps the rest; `browser/client/test_theme.py` receives:

- `test_theme_applies_in_chromium_and_data_pjx_theme_dark_flips_it` (L135-153)
- copied, because both halves use it: `themed` (L43)

Correction to the generated carousel entry: the browser half needs only `_carousel_css`
(copied) and `_track_timing` (moved, nothing else uses it), plus the
`read_pjx_theme_css` import. `session` and `_html` stay in the unit half.

`themed` in `test_pjx_theme_inject.py` is a fixture that turns the theme setting on and
restores it; the copy in `browser/client/test_theme.py` must be the whole fixture. The
comment above `test_theme_off_by_default_leaves_theme_style_unset` ("kept after every
themed test on purpose") still holds: that test stays last in `unit/client/test_inject.py`.

## 5. Markers, pyproject and CI

### 5.1 `pyproject.toml`

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--import-mode=importlib"]
markers = [
    "browser: needs a Playwright chromium page (tests/browser)",
    "docs: checks documentation and its examples (tests/docs)",
    "slow: starts subprocesses or whole apps (tests/scripts, tests/packaging, tests/apps)",
]
```

`--import-mode=importlib` is required, not cosmetic. Today pytest names each test module
by its bare file name, so two files called `test_assets.py` cannot coexist unless a
folder has an `__init__.py`. The new layout has such pairs on purpose
(`unit/test_registry.py` and `unit/discovery/test_registry.py`; `unit/assets/` and
`unit/reactive/test_assets.py`; `unit/builtins/test_pjx_button.py` and
`browser/builtins/test_pjx_button.py`). With importlib mode a module is named by its
path (`tests.unit.reactive.test_assets`), no `__init__.py` is needed anywhere, and the
two existing ones are removed. The whole suite was run
with `--import-mode=importlib` on the current layout and gave the baseline result exactly.

What changes under it: a class defined in a test module reports `__module__` as
`tests.unit.test_x` instead of `test_x`. Discovery breaks tag ties by qualified class
name, and some messages print it, so this was the main thing the experiment looked for.

### 5.2 Applying the markers

In `tests/conftest.py`:

```python
TESTS = Path(__file__).parent
FOLDER_MARKERS = {
    "browser": "browser",
    "docs": "docs",
    "scripts": "slow",
    "packaging": "slow",
    "apps": "slow",
}


def pytest_collection_modifyitems(items):
    for item in items:
        folder = item.path.relative_to(TESTS).parts[0]
        if folder in FOLDER_MARKERS:
            item.add_marker(FOLDER_MARKERS[folder])
```

Expected selections once everything has moved:

| Command | Collected |
|---|---|
| `uv run pytest -m browser --co -q \| tail -1` | 971 |
| `uv run pytest -m "not browser" --co -q \| tail -1` | 5325 |
| `uv run pytest -m docs --co -q \| tail -1` | 103 |
| `uv run pytest -m slow --co -q \| tail -1` | 488 |
| `uv run pytest -m "not browser and not slow and not docs" --co -q \| tail -1` | 4734 |

Measured time per folder in the baseline run: browser 268s, unit 31s, docs 5s, apps 5s,
scripts 2s, packaging 1s. So `-m "not browser"` is the fast loop (under a minute), and
`slow` does not buy much today (question 3).

### 5.3 CI

| File:line | Old | New |
|---|---|---|
| `.github/workflows/tests.yml:30-34` | two steps: `uv run pytest tests/pyjinhx/` then `uv run pytest tests/` | two steps: `uv run pytest -m "not browser"` then `uv run pytest -m browser` |
| `.github/workflows/tests.yml:70` | `.venv-min/bin/python -m pytest tests/minimal/ -q` | `.venv-min/bin/python -m pytest tests/packaging/test_minimal_install.py -q` |
| `.github/workflows/docs-check.yml:35` | `uv run pytest tests/pyjinhx/test_docs_reference_real_fields.py -q` | `uv run pytest tests/docs/test_reference_real_fields.py -q` |

The first row changes what CI does: today `tests/pyjinhx/` runs twice (once alone, once
inside `tests/`). The new pair runs every test once and fails early on the quick half
(question 4). If the maintainer wants the old shape kept, the literal translation is
a single `uv run pytest`.

The minimal leg names one file on purpose. `tests/packaging/` also holds
`test_package_layout.py`, which runs `git ls-files` and is not meant for that leg. The
leg has no pytest-playwright; nothing it loads (`tests/conftest.py`, the one test file)
imports it.

`ruff.yml` runs over the whole repo and needs no change.

## 6. Steps

After every step: `uv run pytest --co -q | tail -1` must still say 6296 collected, then
the listed check, then commit. The quick loop while browser tests are not involved is
`uv run pytest -q -k "not chromium"` (every browser test id ends in `[chromium]`), about
50 seconds, expected `5320 passed, 1 skipped, 3 xfailed, 1 xpassed`. Run the full suite
at the steps that say so.

### Step 1. Import mode

1. Add the `[tool.pytest.ini_options]` block from 5.1.
2. `git rm tests/pyjinhx/client/__init__.py tests/pyjinhx/integrations/__init__.py`.

Check: full suite, same summary as the baseline.

### Step 2. Root conftest

1. `git mv tests/pyjinhx/conftest.py tests/conftest.py`
2. Fix the two `Write` imports (3.1).

Check: full suite. This is the step that widens the four autouse fixtures (4.1).

### Step 3. Fixtures

3.1 Templates folder. `git mv tests/templates tests/fixtures/templates`, then in the
test files (still at their old paths) insert `/ "fixtures"` before `/ "templates"`:

```
git grep -lE '\.parent / "templates"' -- tests | xargs sed -i 's|\.parent / "templates"|.parent / "fixtures" / "templates"|'
```

`test_fastapi_wiring.py:31-33` spreads the expression over three lines; edit it by
hand. `test_render_public.py:209` is fixed in step 4 with its file. Fix
`test_session.py:213, 217` (3.2). Check: `git grep -n 'tests/templates\|/ "templates"' -- tests`
shows only lines that already contain `"fixtures"` and `tmp_path` uses; quick loop.

3.2 Topics. For each row of 2.4, `git mv` the file into its topic folder (`cycle_badge.css`
and `.js` go with `cycle_badge.pjx`). Then apply 3.3: prefix each listed literal with its
topic, in both quote styles, skipping the ten "left alone" lines. Keep the
`build_registry` root in `test_reactive_request_cycle.py` on the templates folder (3.3).
Check: `ls tests/fixtures/templates` shows only folders; quick loop.

3.3 Header helpers. `git mv tests/pyjinhx/header_names.py tests/pyjinhx/header_import_probe.py tests/fixtures/`,
then the sed in 3.1. Check: `uv run pytest tests/pyjinhx/test_props_header_build.py tests/pyjinhx/test_props_header_parse.py tests/pyjinhx/test_classless_factory.py -q`.

3.4 Bench fixtures. `mkdir tests/fixtures/bench`, add an empty `__init__.py`, `git mv` the
three `tests/fixtures/bench_*` files into it, fix the import (3.1). The two `.pjx` files
must stay beside `bench_builtin_heavy.py`: its classes find them by the
template-beside-the-module rule. Check: `uv run pytest tests/test_bench_fixture_parity.py -q`.

### Step 4. Move test files (`git mv` only, one commit per sub-step)

For each sub-step: `git mv` every row of 2.1 whose new path is in that folder and whose
note is empty or "merge 1/n" (the first source of a merge takes the merged file's name
now, so history follows it). Sources marked "merge 2/n" or later and the fourteen mixed
files move too, under their old file names, into the folder of their target; steps 5
and 6 finish them. Then fix that folder's rows of 3.2.

| Sub-step | Folder | Notes | Check |
|---|---|---|---|
| 4.1 | `tests/apps/todo/` | `git mv tests/examples tests/apps/todo`, then rename by glob: `for f in tests/apps/todo/test_todo_*.py; do git mv "$f" "${f/test_todo_/test_}"; done`. The conftest travels with the folder; add `todo_registry` to it (7.1). | `uv run pytest tests/pyjinhx/test_fewer_files_startup.py tests/apps/todo -q` -> 73 passed (that order fails without the fixture) |
| 4.2 | `tests/packaging/` | `git mv tests/minimal/*.py` by glob; if the folder holds one test file, name it `test_minimal_install.py`. Fix the two skip entries in `test_package_layout.py` (3.2). | `uv run pytest tests/packaging -q` -> 250 |
| 4.3 | `tests/apps/fewer_files/` | No path edits: both files anchor on the fixture package. | `uv run pytest tests/apps -q` -> 129 |
| 4.4 | `tests/scripts/` | | `uv run pytest tests/scripts -q` -> 109 |
| 4.5 | `tests/docs/` | `broken_demo.pjx` moves with `test_gallery_demos.py` (section 7.4). | `uv run pytest tests/docs -q` -> 103 |
| 4.6 | `tests/unit/` core modules and their folders | `stale_card.pjx` and `stale_badge.pjx` move with `test_stale_header_warning.py`. `test_registry.py` -> `discovery/test_registry.py` must happen before `test_instance_registry.py` -> `unit/test_registry.py`. | quick loop |
| 4.7 | `tests/unit/reactive/`, `integrations/`, `client/` | | quick loop |
| 4.8 | `tests/unit/builtins/` | Move the graph and roster picker conftests here (4.2) and add `session` to `tests/conftest.py` in the same commit. | `uv run pytest tests/unit -q -k "not chromium"` |
| 4.9 | `tests/browser/` | Create `tests/browser/conftest.py` first, then `client/conftest.py` and `builtins/pjx_graph/conftest.py` (4.2); delete the chart conftest. | full suite |

After 4.9, `tests/pyjinhx/`, `tests/examples/`, `tests/minimal/` and `tests/templates/`
hold no tracked files: `git ls-files tests/pyjinhx tests/examples tests/minimal tests/templates`
prints nothing. Remove what is left of them on disk (`__pycache__`).

### Step 5. Split the mixed files

One commit per file or per builtin, following 4.3. For each: create the browser file
with the listed tests and helpers, delete them from the unit file, trim imports.

Check per file: `uv run pytest <both files> --co -q | tail -1` equals the count the old
file collected; `uv run pytest tests/unit --co -q -k chromium | tail -1` trends to zero
and is `no tests collected` when the step is done. Full suite at the end of the step.

### Step 6. Merge

One commit per row of 2.2. Append the later sources to the file that already has the
merged name, in the listed order, each under a one-line comment naming its subject only
if the file reads better for it; hoist imports to the top; apply the two renames in 2.2;
`git rm` the emptied sources. Do not reorder tests within a source.

Check per merge: the merged file collects the sum in 2.2 and passes; `ruff check` on it
is clean. Full suite at the end of the step.

### Step 7. Markers, CI, prose

1. Add the hook from 5.2 to `tests/conftest.py`.
2. Apply 5.3 and 3.4.

Check: the five counts in 5.2; `uv run mkdocs build --strict` (docs prose was touched).

### Step 8. Final verification

```
uv run pytest --co -q | tail -1                                   # 6296 tests collected
uv run pytest --co -q | grep :: | sed 's/^[^:]*:://' | sort > /tmp/names.after
diff /tmp/names.before /tmp/names.after                           # empty
uv run pytest -q | tail -1                                        # 6291 passed, 1 skipped, 3 xfailed, 1 xpassed
git grep -nE 'tests/(pyjinhx|templates|minimal|examples)\b|tests\.pyjinhx' -- . ':!CHANGELOG.md' ':!docs/superpowers'   # empty
git ls-files tests | grep -vE '^tests/(conftest\.py|unit|browser|docs|scripts|packaging|apps|fixtures)(/|$)'             # empty
find tests -name '*.py' -not -path '*/fixtures/*' -not -name 'test_*' -not -name conftest.py                              # empty
ruff format --check . && ruff check .
```

The `names` diff is the strongest check: it compares every test's class, function and
parameter id while ignoring its file, so a test lost or duplicated by a split or merge
shows up as a line.

## 7. Risks

### 7.1 Test order changes everywhere

Files run in path order, and every path changes, so any test that passes only because
of what ran before it can start failing. The suite has process-wide state (the
discovery registry, the integrations backend slot, `sys.modules`, the cost verdicts),
and several fixtures leave the registry populated on purpose.

This was tested by running the current files in the order the new paths give them
(apps, browser, docs, packaging, scripts, unit; merged sources in merge order), together
with the new import mode and the widened autouse fixtures. Result: **5 failures**, all in
the todo app tests:

```
tests/examples/test_todo_app.py::TestIndex::test_renders_every_seeded_todo
tests/examples/test_todo_app.py::TestIndex::test_children_are_tag_nested_and_id_stamped
tests/examples/test_todo_app.py::TestAdd::test_a_follow_up_page_load_shows_it
tests/examples/test_todo_templates.py::TestApp::test_renders_the_whole_tree
tests/examples/test_todo_templates.py::TestApp::test_children_render_id_stamped_from_their_tags
```

The cause is already in the suite today and has nothing to do with the import mode:

```
uv run pytest tests/pyjinhx/test_fewer_files_startup.py tests/examples -q    # 5 failed, 68 passed, on master
```

`examples/todo/app.py` publishes its components once, when the module is first
imported. The fewer-files tests end by emptying the registry, so any todo test that
runs after them renders `<Counter/>` and friends as unresolved tags. Today nothing runs
before `tests/examples/` (it sorts first). In the new layout `apps/fewer_files/` sorts
before `apps/todo/`.

Fix, added to `tests/apps/todo/conftest.py` in step 4.1:

```python
@pytest.fixture(autouse=True)
def todo_registry():
    """Publish the todo app's components for every test."""
    # The app publishes them once, at import. Tests elsewhere empty the
    # registry, which would leave these rendering their child tags unresolved.
    setup(components_root=Path(todo.__file__).parent / "components")
```

(`from pyjinhx import setup`, `from examples import todo`.) It makes the same call the
app makes, with the folder located from the package rather than from the working
directory, so it keeps working whatever shape `refactor/examples-sfc` gives the
components. With that fixture in place the same run (new order, new
import mode, widened autouse fixtures) gives the baseline result exactly:
`6291 passed, 1 skipped, 3 xfailed, 1 xpassed`.

### 7.2 Autouse fixtures reaching further

Three kinds, all listed above: the four root fixtures (4.1), the chromium guard (4.2),
and module-level autouse fixtures that cover more tests once files merge. The merges
that carry one:

| Merged file | Autouse fixture | Now also covers | Trial result |
|---|---|---|---|
| `unit/test_responses.py` | `_publish_registry` from `test_compose_fanout.py` (publishes three widget classes) | the 12 tests of `test_responses.py` | pass |
| `unit/builtins/test_builtins.py` | `reset_registry` from `test_builtin_autoregistration.py` | the 4 tests of `test_builtin_extra_attrs.py` | pass |
| `browser/builtins/test_pjx_chip_input.py` | `_require_chromium` | 2 tests, which now have it from the conftest anyway | not trialled (browser) |
| `unit/test_config.py` + dispatch | `_empty_backend_registry` | 53 config tests | **fails; merge dropped** (2.2) |

Anyone adding a merge later should check for autouse fixtures first; the dropped one
shows the failure is real and not obvious from reading.

### 7.3 Module-level state in merged files

`test_props_header_parse.py` and `test_props_header_build.py` both pop
`tests.fixtures.header_import_probe` from `sys.modules` and assert on whether it is
imported. Each test pops before asserting, so they stay independent in one file (trial:
118 pass). `unit/integrations/test_base.py` reads its own source and fails if the words
for the web framework appear more than once each; `integrations/test_registry.py`
contains neither, so appending it is safe, but nothing that names the framework may be
merged into that file later.

### 7.4 Templates found beside the test module

A component class with no explicit template resolves `<snake_case_name>.pjx` in the
folder of the module that defines it. Three tracked templates exist only for that:
`stale_card.pjx` and `stale_badge.pjx` (classes in `test_stale_header_warning.py`, which
asserts the resolved path at line 42) and `broken_demo.pjx` (class inside
`test_gallery_demos.py::test_missing_asset_file_fails_the_build`). They must sit in the
same folder as those test files, so they break the "nothing beside tests" rule on
purpose (question 2). If `broken_demo.pjx` goes missing the test still passes, for the
wrong reason: a missing template is also an `OSError`.

Related: `test_sfc_component.py` holds inline templates and asserts on its own path and
line contents, so it is moved but never merged into; `test_component_descriptor.py`
asserts on `Path(__file__).parent` in ten places, which follows the file.

### 7.5 Two files trade a name

`unit/test_registry.py` is today's `test_instance_registry.py` (it tests
`pyjinhx/registry.py`), while today's `test_registry.py` (the discovery registry) becomes
`unit/discovery/test_registry.py`. Do the moves in the order given in step 4.6 and
expect `git log --follow` to need the old name for either.

### 7.6 Fixture names defined in several places

`session` (over forty definitions), `parse_html` (two, different), `page_errors` (four),
`_require_chromium` (26), `themed` (three modules). Section 4 says which one each test
ends up with; in every case it is the same body it uses today. The rule to keep in mind
is that pytest picks the closest definition: module, then the nearest conftest upward.

### 7.7 The byte-compared assets

`pjx_popover.js` and `pjx_select.js` share a block that two tests compare byte for byte,
and each carries a comment naming the other's test file. Editing only one comment
breaks those tests (3.4).

### 7.8 What was not verified

The moves themselves were not performed. The experiments ran the existing files with
the new import mode, the widened autouse fixtures and the new order, and trial-built the
non-browser merges. The order experiment sorts tests into their new files (the two halves
of a mixed file included) but cannot make a merged file's sources share module-level
fixtures; the scratch trial covers that part, for the non-browser merges only. The path edits in section 3 and the splits in 4.3 are derived by script from the
sources and have not been executed.

## 8. Questions for the maintainer

1. Twelve existing files are over 800 lines (section 1), the largest 2659. This plan
   moves them whole. Should a follow-up split them, and should that include the
   function-style ones (`test_reactive_fanout.py`, `test_manifest.py`, `test_session.py`)
   where helpers are interleaved with tests?
2. `stale_card.pjx`, `stale_badge.pjx` and `broken_demo.pjx` stay beside their tests
   (7.4). The alternative is to move the two `Stale*` classes into a
   `tests/fixtures/stale_header/` package and give `BrokenDemo` an inline template, which
   edits test code. Keep the exception, or move them?
3. `slow` is applied to `scripts/`, `packaging/` and `apps/`, which together take about
   8 seconds. Is that the intended meaning, or should each folder simply carry its own
   name as a marker (`scripts`, `packaging`, `apps`, `unit`)?
4. CI today runs `tests/pyjinhx/` twice. The plan replaces that with one fast step and
   one browser step. Acceptable?
5. `unit/slots/` is a feature folder, not a source module. The alternative is to put the
   five slot files in `unit/rendering/` (fifteen files in one folder). Preference?
6. `unit/builtins/pjx_graph/` and `pjx_roster_picker/` group several source modules so
   each family can share its `parse_html`. Fine, or flatten them and give the two
   fixtures different names?
