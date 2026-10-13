# ADR 0005: Roster picker is its own builtin family, fed by items

**Status:** Accepted, 2026-10-13. Unreleased.

## Context

`PJXRosterPicker` is a multi-picker searched on the server. The user types,
the server sends back rows, and each pick becomes a removable chip whose hidden
input posts with the form. It needs an overlay result list placed like the
other overlays, and it reports what the user did through events.

Four choices shaped it: where it lives relative to `PJXSelect`, how chips are
passed in, how its JavaScript gets the shared placement code, and what its
events carry.

## Decision: a separate family, not a `PJXSelect` mode

`PJXSelect` renders a fixed `options` list of `SelectOption`
(`pyjinhx/builtins/ui/pjx_select/pjx_select.py`). The picker owns none of its
options: it sends `q`, `exclude` and `picker_id` to an app route that answers
with `PJXRosterResults`, pages long lists with a `PJXLazyLoad` sentinel, and
keeps the selection as chips. `PJXSelect` is unchanged.

## Decision: `items`, not nested chip markup

The picker and the results take `items: list[PJXRosterItem]`, a frozen pydantic
model (`pyjinhx/builtins/ui/pjx_roster_picker/item.py`) with `value`, `label`,
`subtitle`, `initials`, `color`, `src`, `icon` and two `Slot`s, `extra` and
`detail`. The picker builds one `PJXRosterChip` per item, so the form `name`,
`disabled` and `remove_label` are stated once on the picker. This is the
pattern `SelectOption` already uses.

`PJXRosterChip` stays public, so an app can render one by hand for a custom
layout.

## Decision: a generated JS asset that embeds `popoverPosition`

A builtin ships exactly one script: the asset walk resolves one per class by
stem (see `tests/pyjinhx/builtins/pjx_popover/test_pjx_popover_assets.py`). So
the shared `pjx_popover/pjx_popover_position.js` cannot ride along, and
`pjx_popover.js` and `pjx_select.js` each carry a byte-identical copy of it,
kept in step by tests.

The picker does not add a third copy. `scripts/build_pjx_roster_picker_js.py`
writes `pjx_roster_picker.js` as a banner, then `pjx_popover_position.js`, then
`src/picker.js`. The generated file is committed, and
`tests/pyjinhx/builtins/pjx_roster_picker/test_pjx_roster_picker_js_build.py`
fails when it no longer matches a fresh build. The graph's
`scripts/build_pjx_graph_js.py` works the same way.

## Decision: event `detail` carries the value

Events fire on the picker root and bubble. `before-pick`, `pick`,
`before-remove` and `remove` carry `{value}`; `change` carries `{values}`, the
whole selection in chip order. `before-*` are cancelable.

The overlay builtins send `{reason, trigger}`, but a pick has no dismiss
reason. The value is what the form posts and what the app's data is keyed
by, the way graph events carry node ids.

## Rejected: a searchable or multiple mode on `PJXSelect`

It would put two engines, a static list and a server search with chips, behind
one set of props, and every `PJXSelect` user would pay for the second.

## Rejected: chips as nested markup

Each chip would repeat `name`, `disabled` and `remove_label`, and a chip that
forgot one would post wrongly or stay removable on a disabled picker. The cost
of `items`: a `.pjx` tag cannot pass a list of models, so an app builds the
picker in Python, as it does for `PJXSelect.options`.

## Rejected: a third hand-kept copy of `popoverPosition`

A third copy is a third place for a placement fix to be missed. A separate
shared script was rejected too: the app would have to load it before the
picker, which builtins never ask for.

## Rejected: `{reason, trigger}` or the chip element in `detail`

There is no reason to report. A chip element can be replaced by a swap; the
value cannot.

## Consequences

- `PJXSelect` and `PJXPopover` still hold hand-kept copies of
  `popoverPosition`. Moving them to a build like the picker's is a separate
  change.
- Editing `src/picker.js` or `pjx_popover_position.js` means rerunning
  `scripts/build_pjx_roster_picker_js.py`, or CI fails.
- A picker with items is built in Python, not written as a `.pjx` tag.
- Listeners read `event.detail.value` or `event.detail.values`, never a DOM
  node.

## Related

- [Roster picker](../guide/roster-picker.md) — the components, the search
  route contract and the events.
- [Events and JavaScript API](../guide/roster-picker.md#events-and-javascript-api)
  — the event table this ADR explains.
- [Builtin conventions](../guide/builtin-conventions.md) — the contract every
  builtin follows.
- [ADR 0004](0004-graph-reconcile-model.md) — the graph, whose JS asset is
  built the same way.
