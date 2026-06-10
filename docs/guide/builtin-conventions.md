# Builtin conventions

Every pyjinhx builtin follows the same contract, so knowing one means knowing all of them.

> **Status:** the `px.*` namespace, event vocabulary, and declarative attributes described here land progressively across the 0.8.0 PR stack — this page is the contract the release converges on.

## The contract

1. **`id` is optional.** Omit it and pyjinhx generates `px-<n>`. Pass one when you need a stable
   hook (CSS, htmx targets) — and always for reactive components, whose OOB targeting requires
   stable identity across renders.
2. **`class_name`** appends your classes to the root element: `Badge(label="New", class_name="pill")`.
3. **`extra_attrs`** renders extra attributes (validated — values may not contain `"`) on the root element — the carrier for
   `hx-*`, `data-*`, `aria-*`, or Alpine directives:
   `Card(body=..., extra_attrs={"hx-get": "/refresh", "hx-trigger": "every 30s"})`.
4. **All copy is props.** Every user-visible string, aria-labels included, has an English default
   you can replace: `Modal(title="Excluir?", close_label="Fechar")`.
5. **JS is headless.** Builtin JavaScript never writes inline styles for state — visibility and variants are classes/attributes; computed positioning coordinates (tooltip/popover placement) are the one sanctioned inline-style use. Communication is through `px:*` DOM events and `data-px-*` attributes; programmatic APIs live under the single `window.px` namespace.
6. **The DOM contract is API.** Each builtin's documentation ends with a "DOM contract" block —
   stable classes, `data-px-*` attributes, events, state attributes. We version those like code.

## Events and hooks

Interactive builtins fire a two-tier event vocabulary on their root element (all bubble):

- `px:<component>:before-<verb>` — **cancelable**. `event.preventDefault()` aborts the action.
  `detail = {reason, trigger}` with `reason ∈ {"escape","backdrop","api","trigger"}`.
- `px:<component>:<verb>` — fired after the DOM change. Not cancelable.

Shared vocabulary: `px:before-reveal` / `px:reveal` fire on any `[data-px-region]` (Panel panels,
TabGroup bodies) when it is shown — `LazyPanel(when="reveal")` builds on it; `px:toast` is the
input event ToastHost listens for (htmx fires it from `HX-Trigger` response headers).

```js
document.getElementById("confirm-del").addEventListener("px:modal:before-close", (e) => {
    if (hasUnsavedChanges()) e.preventDefault();
});
```

## Declarative attributes

| attribute | effect |
|---|---|
| `data-px-open="<id>"` | click opens that Modal / Drawer |
| `data-px-close` | click closes the nearest enclosing dismissible |
| `data-px-toggle="<id>"` | click toggles that Popover / Dropdown menu |
| `data-px-confirm-danger` | `hx-confirm` on this element gets a danger-styled OK button |
| `data-px-confirm-ok`, `data-px-confirm-cancel` | per-trigger confirm-dialog label overrides |
| `data-px-loader` | requests from this subtree show the PageLoader |
| `data-px-region` | marks a show/hide region (emits `px:reveal`) |
| `data-px-autoshow` | Notification auto-shows when this attribute is present on mount |

## The `window.px` namespace

`px.modal` · `px.drawer` · `px.popover` · `px.notification` · `px.overlay` (region loading) ·
`px.loader` (page loading) · `px.confirm` · `px.prompt` · `px.toast`. Open/close/show/hide
functions return `false` when a `before-*` hook canceled the action.

## Theming

Builtins read `--px-*` tokens that default to your app-level semantic tokens. Re-skin globally in
one block:

```css
:root {
  --px-modal-bg: var(--surface);
  --px-card-radius: var(--radius-lg);
}
```

or per-context: `.settings-pane { --px-card-bg: var(--surface-alt); }`.
