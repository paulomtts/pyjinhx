# Reactive to-do

A small to-do panel that shows how pyjinhx turns one mutation into a
dependency-aware set of out-of-band swaps.

## Run it

```bash
uv run uvicorn examples.todo.app:app --reload
```

Then open <http://127.0.0.1:8000/>.

## What it demonstrates

Every piece of the panel declares what it reads. `Counter`, `Total`,
`ClearButton` and `ItemRow` are all `react={Keys.TODOS}`; `ItemList` is
`react={Keys.TODO_LIST}`.

The store declares what it writes: `store.add` and `store.toggle` are
`@mutates(Keys.TODOS)`, and `store.clear_completed` is
`@mutates(Keys.TODOS, Keys.TODO_LIST)`. Calling one of them dirties those keys.

Each route then returns a `ReactiveResponse`, which fans the mounted
subscribers of the dirtied keys out as OOB swaps next to the primary fragment.
Subscribers whose rendered output did not actually change are dropped, so the
fan-out is usually smaller than the subscriber list.

Open the network tab, click around, and read the response bodies — the skipped
components are named in HTML comments:

| Action | Primary fragment | Swapped out of band | Skipped |
| --- | --- | --- | --- |
| Toggle a row (`POST /rows/{id}/toggle`) | the row | counter, clear button | total |
| Add a todo (`POST /todos`) | the new row | counter, total | clear button |
| Clear completed (`POST /todos/clear-completed`) | none (`HX-Reswap: none`) | list, total | counter |

## Loading indicators

The `<li>` in `components/item_row/item_row.pjx` carries
`data-pjx-loading="skeleton"`, and the `<button>` in
`components/clear_button/clear_button.pjx` carries
`data-pjx-loading="spinner" data-pjx-loading-extra=".todo.done"`.

Nothing here is artificially slowed down, so against a local store the
indicators flash by; throttle the network tab to watch them. See
[docs/reactivity.md](../../docs/reactivity.md) for what the attributes do.
