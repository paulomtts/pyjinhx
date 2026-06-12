# Builtin conventions

Every pyjinhx builtin follows the same contract, so knowing one means knowing all of them.

## The contract

1. **`id` is optional.** Omit it and pyjinhx generates `pjx-<n>`. Pass one when you need a stable
   hook (CSS, htmx targets) — and always for reactive components, whose OOB targeting requires
   stable identity across renders.
2. **`class_name`** appends your classes to the root element: `PJXBadge(label="New", class_name="pill")`.
3. **`extra_attrs`** renders extra attributes (validated — values may not contain `"`) on the root element — the carrier for
   `hx-*`, `data-*`, `aria-*`, or Alpine directives:
   `PJXCard(body=..., extra_attrs={"hx-get": "/refresh", "hx-trigger": "every 30s"})`.
4. **All copy is props.** Every user-visible string, aria-labels included, has an English default
   you can replace: `PJXModal(title="Excluir?", close_label="Fechar")`.
5. **JS is headless.** Builtin JavaScript never writes inline styles for state — visibility and variants are classes/attributes; computed positioning coordinates (tooltip/popover placement) are the one sanctioned inline-style use. Communication is through `pjx:*` DOM events and `data-pjx-*` attributes; programmatic APIs live under the single `window.pjx` namespace.
   Async-state JS follows the runtime's concurrency pattern: a ref-count per scope,
   release keyed to each request's `loadend` (terminal on load, error, abort, and
   timeout), and state re-applied after `htmx:afterSettle` for nodes a swap replaced
   mid-flight.
6. **The DOM contract is API.** Each builtin's documentation ends with a "DOM contract" block —
   stable classes, `data-pjx-*` attributes, events, state attributes. We version those like code.

## Events and hooks

Interactive builtins fire a two-tier event vocabulary on their root element (all bubble):

- `pjx:<component>:before-<verb>` — **cancelable**. `event.preventDefault()` aborts the action.
  `detail = {reason, trigger}` with `reason ∈ {"escape","backdrop","api","trigger"}`.
- `pjx:<component>:<verb>` — fired after the DOM change. Not cancelable.

Shared vocabulary: `pjx:before-reveal` / `pjx:reveal` fire on any `[data-pjx-region]` (PJXPanel panels,
PJXTabGroup bodies) when it is shown — `PJXLazyPanel(when="reveal")` builds on it; `pjx:toast` is the
input event PJXToastHost listens for (htmx fires it from `HX-Trigger` response headers).

```js
document.getElementById("confirm-del").addEventListener("pjx:modal:before-close", (e) => {
    if (hasUnsavedChanges()) e.preventDefault();
});
```

## Declarative attributes

| attribute | effect |
|---|---|
| `data-pjx-open="<id>"` | click opens that PJXModal / PJXDrawer |
| `data-pjx-close` | click closes the nearest enclosing dismissible |
| `data-pjx-toggle="<id>"` | click toggles that PJXPopover / PJXDropdown menu |
| `data-pjx-confirm-danger` | `hx-confirm` on this element gets a danger-styled OK button |
| `data-pjx-confirm-ok`, `data-pjx-confirm-cancel` | per-trigger confirm-dialog label overrides |
| `data-pjx-loader` | requests from this subtree show the PJXPageLoader |
| `data-pjx-region` | marks a show/hide region (emits `pjx:reveal`) |
| `data-pjx-autoshow` | PJXNotification auto-shows when this attribute is present on mount |

## The `window.pjx` namespace

`pjx.modal` · `pjx.drawer` · `pjx.popover` · `pjx.notification` · `pjx.loader.region` (region busy-state) ·
`pjx.loader.page` (page navigation) · `pjx.confirm` · `pjx.prompt` · `pjx.toast`. Open/close/show/hide
functions return `false` when a `before-*` hook canceled the action.

## Theming

Builtins read `--pjx-*` tokens that default to your app-level semantic tokens. Re-skin globally in
one block:

```css
:root {
  --pjx-modal-bg: var(--surface);
  --pjx-card-radius: var(--radius-lg);
}
```

or per-context: `.settings-pane { --pjx-card-bg: var(--surface-alt); }`.
