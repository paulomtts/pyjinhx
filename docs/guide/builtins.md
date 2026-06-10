# Built-in UI components

Optional package **`pyjinhx.builtins`** registers twenty-eight [`BaseComponent`](../api/base-component.md) subclasses. Import:

```python
from pyjinhx.builtins import (
    Alert,
    Avatar,
    AvatarStack,
    Badge,
    Breadcrumb,
    Card,
    ConfirmDialog,
    Divider,
    Dropdown,
    Drawer,
    EmptyState,
    LazyPanel,
    RegionLoader,
    Modal,
    Notification,
    PageLoader,
    Popover,
    PopoverPanel,
    PopoverTrigger,
    Progress,
    PromptDialog,
    Panel,
    PanelTrigger,
    Skeleton,
    Spinner,
    TabGroup,
    ToastHost,
    Tooltip,
)
```

`__all__` matches that set of twenty-eight names.

**Conventions:** Markup classes use the **`px-`** prefix; overrides use **`--px-`** custom properties. Builtin CSS also references **theme variables** (`--surface`, `--border`, `--text`, `--radius-md`, `--shadow-md`, `--transition`, `--brand`, …)—define those in your global CSS or map them to your design system. See [builtin-conventions.md](./builtin-conventions.md) for the full per-component contract (auto-id, `class_name`, `extra_attrs`, `js`/`css`, headless IIFE JS under `window.px`, cancelable `px:*:before-*` events).

**Template discovery:** Builtins ship inside `site-packages`, not under your app's Jinja loader root, so PascalCase tags do **not** auto-discover them — `<Tooltip/>` raises a `FileNotFoundError` unless the class was imported once at startup (`import pyjinhx.builtins` or any of the imports above), which registers it. For registered builtin classes, the renderer **falls back** to adjacent package templates: each component's Jinja template lives next to its Python source in `pyjinhx/builtins/ui/<component>/` (e.g. `pyjinhx/builtins/ui/modal/modal.html`).

**Inherited fields:** Every component inherits **`id`** (optional — omitted/falsy ids become `px-<n>`; reactive components need stable ids, defaulted to the kebab-cased class name; pass explicit ids for instance-keyed rows), **`js`** / **`css`** (extra asset paths), **`render()`**, and **`__html__()`** from [`BaseComponent`](../api/base-component.md). `id` is omitted from per-component props tables below. Every builtin also accepts `class_name` (extra classes appended to the root) and `extra_attrs` (validated `dict[str, str]` rendered on the root element).

**Theming:** Per-component `--px-*` tokens are collected in the [Theming tokens](#theming-tokens) appendix. Each component section points there.

**Asset summary:**

| Component | CSS | JS |
|---|---|---|
| Alert | `alert.css` | `alert.js` |
| Avatar | `avatar.css` | — |
| AvatarStack | `avatar-stack.css` | — |
| Badge | `badge.css` | — |
| Breadcrumb | `breadcrumb.css` | — |
| Card | `card.css` | — |
| ConfirmDialog | `confirm-dialog.css` | `confirm-dialog.js` |
| Divider | `divider.css` | — |
| Drawer | `drawer.css` | `drawer.js` |
| Dropdown | `dropdown.css` | *(via popover.js, extra-asset)* |
| EmptyState | `empty-state.css` | — |
| LazyPanel | — | — |
| RegionLoader | `region-loader.css` | `region-loader.js` |
| Modal | `modal.css` | `modal.js` |
| Notification | `notification.css` | `notification.js` |
| PageLoader | `page-loader.css` | `page-loader.js` |
| Panel | `panel.css` | `panel.js` |
| PanelTrigger | `panel-trigger.css` | *(panel.js from Panel)* |
| Popover | `popover.css` | `popover.js` |
| PopoverPanel | *(from Popover)* | *(from Popover)* |
| PopoverTrigger | *(from Popover)* | *(from Popover)* |
| Progress | `progress.css` | — |
| PromptDialog | `prompt-dialog.css` | `prompt-dialog.js` |
| Skeleton | `skeleton.css` | — |
| Spinner | `spinner.css` | — |
| TabGroup | `tab-group.css` | `tab-group.js` |
| ToastHost | `toast-host.css` | `toast-host.js` |
| Tooltip | `tooltip.css` | `tooltip.js` (IIFE, no API) |

**Children-vs-`content` tag gotcha (children-mapping components):** Several components map children to a single attribute (e.g. Tooltip `tip`, Notification `content`, PanelTrigger `content`). If you use `Renderer.render()` with PascalCase tags, do **not** supply both child text and the corresponding attribute on the same tag—use body text as the child *or* the attribute, not both.

**Backdrop click (Modal and Drawer):** Both render a native `<dialog>`; a document `click` listener treats a click whose target is the `<dialog>` root itself (the backdrop) as a close. Any native `<dialog>` clicked directly is affected—use unique ids and avoid stacking multiple dialogs unless you adjust this.

**`panel.js` loading:** `panel.js` is included only when a [`Panel`](#panel) is rendered on the page. [`PanelTrigger`](#paneltrigger) does **not** load `panel.js` by asset name, so render a `Panel` on the same page (or add the script yourself) for triggers to work.

---

## Badge

Small status label. **Assets:** `badge.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `label` | `str` | `""` | Inner text. |
| `color` | literal | `"neutral"` | `brand`, `error`, `neutral`, `muted` → `px-badge--{color}`. |
| `shape` | literal | `"md"` | `square`, `sm`, `md`, `full` → `px-badge--{shape}`. |

**DOM contract.** Root `.px-badge`; no JS API.

**Classes:** `px-badge`; color modifiers `px-badge--brand`, `--error`, `--neutral`, `--muted`; shape `px-badge--square`, `--sm`, `--md`, `--full`. Theming: see [Badge tokens](#badge-tokens).

---

## Modal

Native `<dialog>`. **Assets:** `modal.css`, `modal.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `title` | `str \| BaseComponent` | `""` | Default header title when `header` is empty. |
| `header` | `str \| BaseComponent` | `""` | If set, replaces the built-in title row. |
| `body` | `str \| BaseComponent` | `""` | Main content; wrapper id `{{ id }}-body`. |
| `footer` | `str \| BaseComponent` | `""` | If non-empty, renders `<footer class="px-modal__footer">`. |
| `close_label` | `str` | `"Close"` | `aria-label` for the close button. |
| `open_on_mount` | `bool` | `False` | When `True`, adds `data-px-open-on-mount`; JS opens the dialog as soon as it mounts (e.g. via `hx-swap="beforeend"`). |
| `remove_on_close` | `bool` | `False` | When `True`, adds `data-px-remove-on-close`; JS removes the element from the DOM on close. |

```html
<button data-px-open="info-modal">Open</button>
<Modal id="info-modal" title="Hello" body="Content here."/>
```

**DOM contract.** Root `dialog.px-modal` (state: `[open]`, `.px-modal--closing`).
Attributes: `data-px-open="<id>"` on any element opens it on click; `data-px-close` inside closes it;
`data-px-open-on-mount`, `data-px-remove-on-close` reflect the lifecycle props.
Events (bubble from the root): `px:modal:before-open`*, `px:modal:open`,
`px:modal:before-close`*, `px:modal:close` — `*` = cancelable, `detail = {reason, trigger}`,
`reason ∈ escape|backdrop|api|trigger`. API: `px.modal.open(id)`, `px.modal.close(id)`.

**Classes:** `px-modal`; closing state `px-modal--closing`; `px-modal__box`, `__header`, `__title`, `__close`, `__body`, `__footer`. Theming: see [Modal tokens](#modal-tokens).

---

## Notification

Fixed-position toast. **Assets:** `notification.css`, `notification.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Message body. |
| `corner` | literal | `"top-right"` | `top-right`, `top-left`, `bottom-right`, `bottom-left`. |
| `timeout` | `int` | `5000` | Auto-dismiss ms; `0` disables. Rendered as `data-timeout`. |
| `autoshow` | `bool` | `True` | When `True`, adds `data-px-autoshow`; JS shows the notification as soon as it mounts. |
| `dismiss_label` | `str` | `"Dismiss"` | `aria-label` for the dismiss button. |

**DOM contract.** Root `.px-notification` (state: `.px-notification--visible`, `.px-notification--hiding`).
`data-px-autoshow` triggers auto-show on mount. `data-px-close` inside hides it.
Events: `px:notification:before-show`*, `px:notification:show`, `px:notification:before-hide`*, `px:notification:hide` — `*` = cancelable, `detail = {reason, trigger}`.
API: `px.notification.show(id)`, `px.notification.hide(id)`.

Maps children to `content`; see the [children-vs-`content` note](#built-in-ui-components).

**Classes:** `px-notification`; placement `px-notification--top-right`, `--top-left`, `--bottom-right`, `--bottom-left`; JS state `px-notification--visible`, `px-notification--hiding`; `px-notification__content`, `px-notification__close`. Theming: see [Notification tokens](#notification-tokens).

---

## Popover

Click-toggle compound. Three separate components; compose them by placing `PopoverTrigger` and `PopoverPanel` **as children inside `Popover`**. **Assets:** `popover.css`, `popover.js` (IIFE under `px.popover`).

```python
Popover(
    id="menu",
    content=str(
        PopoverTrigger(id="menu-t", content="Open") +
        PopoverPanel(id="menu-p", role="menu", content="…")
    ),
)
```

Or with PascalCase tags:

```html
<Popover id="menu">
  <PopoverTrigger id="menu-t">Open</PopoverTrigger>
  <PopoverPanel id="menu-p" role="menu">…</PopoverPanel>
</Popover>
```

### Popover

Root wrapper — sets up the `data-px-popover` attribute scope.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Children (trigger + panel). |
| `align` | literal | `"start"` | `start` or `end` (panel alignment) → `px-popover--align-end`. |
| `behavior` | `bool` | `True` | When `True`, adds `data-px-popover` (JS picks it up). |

### PopoverTrigger

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Button/div label. |
| `tag` | literal | `"button"` | `button` or `div` (role="button"). |
| `role` | literal | `""` | `aria-haspopup` value: `menu`, `listbox`, `dialog`, or `""`. |
| `behavior` | `bool` | `True` | When `True`, adds `data-px-toggle`. |

### PopoverPanel

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Panel body. |
| `as_form` | `bool` | `False` | Render panel as `<form>` instead of `<div>`. |
| `role` | literal | `""` | ARIA `role` attribute (`menu`, `listbox`, `dialog`, or `""`). |
| `behavior` | `bool` | `True` | When `True`, adds `data-px-popover-panel` (hidden by default). |

**DOM contract.** Root `[data-px-popover]` (the Popover wrapper). Trigger: `[data-px-toggle]` on the trigger element; `aria-expanded` synced by JS. Panel: `[data-px-popover-panel]` element, `hidden` when closed. `data-px-close` inside the panel closes it. `data-px-toggle="<panel-id>"` on any element opens/closes a named panel.
Events (bubble from `[data-px-popover]`): `px:popover:before-open`*, `px:popover:open`, `px:popover:before-close`*, `px:popover:close` — `detail = {reason, trigger}`.
API: `px.popover.open(idOrEl)`, `px.popover.close(idOrEl)`, `px.popover.toggle(idOrEl)`.

**Classes:** `px-popover`, `px-popover--align-end`, `px-popover__trigger`, `px-popover__panel`. Theming: see [Popover tokens](#popover-tokens).

---

## RegionLoader

In-place loading veil over a positioned ancestor. **Assets:** `region-loader.css`, `region-loader.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `aria_label` | `str` | `"Loading"` | Accessible label (`role="status"`). |

**Layout:** Overlay is `position: absolute; inset: 0`. Parent must be **`position: relative`** (or any non-`static` value) so coverage is correct.

Also works as an **`hx-indicator`** target: htmx adds `htmx-request` to the element, and the overlay CSS responds to `.px-region-loader.htmx-request` by activating the veil — no JS call required. For programmatic use, `show`/`hide` are **reference-counted per `id`** so overlapping async operations are safe.

**DOM contract.** Root `.px-region-loader` (state: `.px-region-loader--visible`, `.px-region-loader--hiding`; also responds to `.htmx-request` as an htmx indicator).
Events (non-cancelable): `px:region-loader:show`, `px:region-loader:hide`.
API: `px.loader.region.show(id)`, `px.loader.region.hide(id)`, `px.loader.region.reset(id)`.

**Classes:** `px-region-loader`; state `px-region-loader--visible`, `px-region-loader--hiding`; `px-region-loader__spinner`. Theming: see [RegionLoader tokens](#regionloader-tokens).

---

## Tooltip

Compact focus/hover hint. **Assets:** `tooltip.css`, `tooltip.js` (IIFE — no API, behavior only).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `trigger` | `str \| BaseComponent` | `""` | Focusable trigger (`px-tooltip__trigger`, `tabindex="0"`). |
| `tip` | `str \| BaseComponent` | `""` | `role="tooltip"` body. |
| `placement` | literal | `"top"` | `top`, `bottom`, `start`, `end` → `data-px-tooltip-placement`. |

**DOM contract.** Root `.px-tooltip`. `data-px-tooltip-placement` drives JS positioning (`top`/`bottom`/`start`/`end`). Tip shows on `mouseover`/`focusin` of `.px-tooltip__trigger`; hides on `mouseout`/`focusout`; repositions on `scroll`. No JS API (`px._tooltipWired` guard only).

**Classes:** `px-tooltip`, `px-tooltip__trigger`, `px-tooltip__tip`, `px-tooltip__tip--visible`. Maps children to `tip`; see the [children-vs-`content` note](#built-in-ui-components). Theming: see [Tooltip tokens](#tooltip-tokens).

---

## Alert

Inline status banner. **Assets:** `alert.css`, `alert.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `variant` | literal | `"info"` | `info`, `success`, `warning`, `error` → `px-alert--{variant}`. |
| `title` | `str` | `""` | Optional heading. |
| `body` | `str \| BaseComponent` | `""` | Main copy. |
| `dismissible` | `bool` | `False` | When `True`, renders a dismiss button with `data-px-close`. |
| `dismiss_label` | `str` | `"Dismiss"` | `aria-label` for the dismiss button. |

**DOM contract.** Root `.px-alert` (state: `.px-alert--dismissed` — set by JS, hides via `display: none`).
`data-px-close` inside triggers dismissal.
Events: `px:alert:before-dismiss`* (cancelable), `px:alert:dismiss` — `detail = {reason: 'trigger', trigger}`.

**Classes:** `px-alert`; variant modifiers `px-alert--info`, `--success`, `--warning`, `--error`; dismissed state `px-alert--dismissed`; `px-alert__inner`, `__text`, `__title`, `__body`, `__dismiss`. Variants use `color-mix` with `--brand`, `--success`, `--warning`, or `--error` / `--error-bg` / `--error-border` where applicable. Theming: see [Alert tokens](#alert-tokens).

---

## Dropdown

Button + anchored panel backed by the shared popover engine. **Assets:** `dropdown.css` only (ships no own JS — `popover.js` is included via the `js` extra-asset field whenever a Dropdown renders).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `trigger` | `str \| BaseComponent` | `""` | Button label. |
| `items` | `list[str \| BaseComponent]` | `[]` | Menu items rendered inside the panel. |
| `align` | literal | `"start"` | `start` or `end` → `px-dropdown--align-end`. |
| `menu_label` | `str` | `"Submenu"` | `aria-label` on the menu panel. |
| `behavior` | `bool` | `True` | When `False`, removes all `data-px-*` wiring. |

Trigger id is `{{ id }}-trigger`, menu is `{{ id }}-menu`.

**DOM contract.** Root `.px-dropdown` with `data-px-popover`. Trigger: `button.px-dropdown__trigger` with `data-px-toggle="{{ id }}-menu"`, `aria-expanded` synced by `popover.js`. Panel: `div.px-dropdown__menu[data-px-popover-panel][role="menu"]`, `hidden` when closed. All popover events and API apply: `px.popover.open/close/toggle(panelId)`. Document click outside closes the menu; `Escape` closes all open popovers.

**Classes:** `px-dropdown`, `px-dropdown--align-end`, `px-dropdown__trigger`, `px-dropdown__menu`. Theming: see [Dropdown tokens](#dropdown-tokens).

---

## Drawer

`<dialog>` sheet from an edge. **Assets:** `drawer.css`, `drawer.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `side` | literal | `"right"` | `left`, `right`, or `bottom` → `px-drawer--{side}`. |
| `title` | `str \| BaseComponent` | `""` | Header title. |
| `body` | `str \| BaseComponent` | `""` | Scrollable body. |
| `footer` | `str \| BaseComponent` | `""` | Optional footer strip. |
| `close_label` | `str` | `"Close"` | `aria-label` for the close button. |
| `open_on_mount` | `bool` | `False` | Adds `data-px-open-on-mount`; JS opens on arrival. |
| `remove_on_close` | `bool` | `False` | Adds `data-px-remove-on-close`; JS removes element on close. |

**DOM contract.** Root `dialog.px-drawer` (state: `[open]`, `.px-drawer--closing`).
`data-px-open="<id>"` on any element opens it; `data-px-close` inside closes it;
`data-px-open-on-mount`, `data-px-remove-on-close` reflect lifecycle props.
Events: `px:drawer:before-open`*, `px:drawer:open`, `px:drawer:before-close`*, `px:drawer:close` — `*` = cancelable, `detail = {reason, trigger}`, `reason ∈ escape|backdrop|api|trigger`.
API: `px.drawer.open(id)`, `px.drawer.close(id)`.

**Classes:** `px-drawer`; side modifiers `px-drawer--left`, `--right`, `--bottom`; closing state `px-drawer--closing`; `px-drawer__box`, `__header`, `__title`, `__close`, `__body`, `__footer`. Backdrop click closes the dialog (see [intro note](#built-in-ui-components)). Theming: see [Drawer tokens](#drawer-tokens).

---

## Progress

Determinate or indeterminate meter. **Assets:** `progress.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `value` | `float \| None` | `None` | Omit or `None` for indeterminate `<progress>`. |
| `max` | `float` | `100` | Passed to `<progress max="…">`. |
| `label` | `str` | `""` | Optional `px-progress__label`; wires `aria-labelledby` when set. |

**DOM contract.** Root `.px-progress`; no JS API.

**Classes:** `px-progress`, `px-progress__label`, `px-progress__bar`. Theming: see [Progress tokens](#progress-tokens).

---

## Skeleton

Placeholder shimmer blocks. **Assets:** `skeleton.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `variant` | literal | `"text"` | `text` (stacked lines), `circle`, or `rect`. |
| `lines` | `int` | `3` | For `text`, count of `px-skeleton__line` rows. |

**DOM contract.** Root `.px-skeleton`; no JS API.

**Classes:** `px-skeleton`; variant modifiers `px-skeleton--text`, `--circle`, `--rect`; `px-skeleton__line`, `px-skeleton__circle`, `px-skeleton__rect`. Theming: see [Skeleton tokens](#skeleton-tokens).

---

## EmptyState

Centered empty view. **Assets:** `empty-state.css` only (template file **`empty-state.html`** next to `empty_state.py`).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `image` | `str \| BaseComponent` | `""` | Optional slot above the heading (e.g. illustration markup). |
| `title` | `str \| BaseComponent` | `""` | Heading. |
| `description` | `str \| BaseComponent` | `""` | Supporting text. |
| `action` | `str \| BaseComponent` | `""` | Optional slot (e.g. button markup). |
| `actions` | `list[str \| BaseComponent]` | `[]` | Optional flex row of slots; renders after `action` when both are set. |

**DOM contract.** Root `.px-empty-state`; no JS API.

**Classes:** `px-empty-state`, `px-empty-state__image`, `px-empty-state__title`, `px-empty-state__desc`, `px-empty-state__action`, `px-empty-state__actions`. Theming: see [EmptyState tokens](#emptystate-tokens).

---

## LazyPanel

HTMX lazy-load wrapper: a single `div` that fetches `url` on a computed trigger and swaps itself with the response. **Assets:** none.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `url` | `str` | required | Endpoint for the deferred content (`hx-get`). |
| `when` | literal | `"viewport"` | `viewport` (scroll-revealed), `reveal` (`px:reveal` from nearest `[data-px-region]`), `load` (immediately). Overridden by `trigger`. |
| `trigger` | `str` | `""` | Explicit `hx-trigger` value; overrides `when` entirely when set. |
| `swap` | `str` | `"outerHTML"` | `hx-swap` strategy. |
| `content` | `str \| BaseComponent` | `""` | Placeholder shown until the fetch lands (e.g. a [`Skeleton`](#skeleton)). |

`when` preset mapping:

| `when` | `hx-trigger` value |
| --- | --- |
| `viewport` (default) | `revealed` |
| `reveal` | `px:reveal from:closest [data-px-region] once` |
| `load` | `load` |

```python
LazyPanel(id="comments", url="/posts/42/comments", content=Skeleton(id="comments-skel"))
```

**DOM contract.** Root `.px-lazy-panel`; no JS (pure HTMX). `data-px-region` on a Panel or PanelTrigger host fires `px:reveal`/`px:before-reveal` events that `when="reveal"` listens for.

**Classes:** `px-lazy-panel` (unstyled hook). No theming tokens.

---

## Divider

Separator line. **Assets:** `divider.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `orientation` | literal | `"horizontal"` | `horizontal` (default `hr`) or `vertical` (bar). |
| `label` | `str` | `""` | If set with horizontal orientation, flex row with label between lines. |

**DOM contract.** Root `.px-divider`; no JS API.

**Classes:** `px-divider--horizontal`, `px-divider--vertical`, `px-divider--labeled`, `px-divider__line`, `px-divider__label`. Theming: see [Divider tokens](#divider-tokens).

---

## Spinner

Inline loading indicator. **Assets:** `spinner.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `size` | literal | `"md"` | `sm`, `md`, or `lg`. |
| `label` | `str` | `"Loading"` | Visually hidden; exposed to assistive tech. |

**DOM contract.** Root `.px-spinner`; no JS API.

**Classes:** `px-spinner`, `px-spinner--sm|md|lg`, `px-spinner__ring`, `px-spinner__label` (screen-reader-only). Theming: see [Spinner tokens](#spinner-tokens).

---

## Avatar

Image or initials in a circle. **Assets:** `avatar.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `src` | `str` | `""` | Image URL; when empty, initials fallback is shown. |
| `alt` | `str` | `""` | `img` alt text; also used as `title` on initials. |
| `initials` | `str` | `""` | Up to two characters (trimmed/capped in validation). |
| `size` | literal | `"md"` | `sm`, `md`, or `lg`. |
| `color` | `str` | `""` | Extra class or inline color hint (appended to root classes). |

**DOM contract.** Root `.px-avatar`; no JS API.

**Classes:** `px-avatar`, `px-avatar--sm|md|lg`, `px-avatar__img`, `px-avatar__initials`. Theming: see [Avatar tokens](#avatar-tokens).

---

## Card

Grouped content with optional header and footer. **Assets:** `card.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `title` | `str \| BaseComponent` | `""` | Default header title (ignored if `header` is set). |
| `header` | `str \| BaseComponent` | `""` | Custom header slot; replaces `title` block when set. |
| `body` | `str \| BaseComponent` | `""` | Main content. |
| `footer` | `str \| BaseComponent` | `""` | Optional footer. |

**DOM contract.** Root `.px-card`; no JS API.

**Classes:** `px-card`, `px-card__header`, `px-card__title`, `px-card__body`, `px-card__footer`. Theming: see [Card tokens](#card-tokens).

---

## Breadcrumb

Ordered trail of links. **Assets:** `breadcrumb.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `items` | `list[tuple[str, str \| None]]` | `[]` | `(label, href)` left to right; `href` `None` marks the current page. |

`items` may also be passed as a **JSON array** string (e.g. from PascalCase tags): `[["Home","/"],["Here",null]]`.

**DOM contract.** Root `.px-breadcrumb`; no JS API.

**Classes:** `px-breadcrumb`, `px-breadcrumb__list`, `px-breadcrumb__item`, `px-breadcrumb__link`, `px-breadcrumb__current`. Separators via `::after` on items except the last. Theming: see [Breadcrumb tokens](#breadcrumb-tokens).

---

## TabGroup

Tab buttons and panels. **Assets:** `tab-group.css`, `tab-group.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `tabs` | `dict[str, str \| BaseComponent]` | `{}` | **Insertion order** is tab order; keys are labels, values are panel bodies. |
| `tabs_label` | `str` | `"Tabs"` | `aria-label` for the tab list. |

`tabs` may also be a **JSON object** string from markup tags (values are HTML strings).

**DOM contract.** Root `.px-tab-group` with `data-px-region` (fires `px:reveal`/`px:before-reveal` on panel switch). Tab elements: `.px-tab-group__tab` with `data-px-panel-key`; panel elements: `.px-tab-group__panel[data-px-region]`. `px:before-reveal` (cancelable) fires before switching; `px:reveal` fires after; `data-px-revealed` is set on the visible panel. `tab-group.js` delegates `click` within `.px-tab-group__list`, updates `aria-selected`, `tabindex`, and `hidden`.

**Classes:** `px-tab-group`, `px-tab-group__list`, `px-tab-group__tab`, `px-tab-group__panel`. Theming: see [TabGroup tokens](#tabgroup-tokens).

---

## Panel

Host for **distributed** tab-like switching: all bodies render here; controls are separate [`PanelTrigger`](#paneltrigger) components. **Unstyled** aside from `hidden` panels. **Assets:** `panel.css`, `panel.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `panels` | `dict[str, str \| BaseComponent]` | `{}` | **Insertion order** sets the initially visible slot (first is shown). Keys must match `[a-zA-Z0-9_-]+`. |

`panels` may be a **JSON object** string from PascalCase tags. Keys are used in HTML `id` attributes and `data-px-panel-key`. Slot element ids are `{{ id }}-panel-{{ key }}`. The `id` must match `PanelTrigger.panel_id`.

**DOM contract.** Root `.px-panel` with `id`. Panels: `.px-panel__panel[data-px-panel-key][data-px-region]`. Events (bubble from the active panel): `px:before-reveal`* (cancelable, `detail = {reason, trigger}`), `px:reveal`; `data-px-revealed` on the visible panel. `panel.js` click delegation on `.px-panel-trigger`; `pxPanelInit` runs on `DOMContentLoaded`, `htmx:afterSwap`, `htmx:afterSettle`.

**Classes:** `px-panel`, `px-panel__panel`. No theme tokens; minimal rules for `[hidden]` panels.

---

## PanelTrigger

Invisible wrapper that wires clicks to a [`Panel`](#panel) slot. **Assets:** `panel-trigger.css`. See the [`panel.js` loading note](#built-in-ui-components)—render a `Panel` on the same page so the script is included.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `panel_id` | `str` | (required) | Must equal the target `Panel.id`. |
| `panel` | `str` | (required) | Key matching a key in `Panel.panels`; `[a-zA-Z0-9_-]+`. |
| `content` | `str \| BaseComponent` | `""` | Inner HTML / nested components (your visible control). |

Maps children to `content`; see the [children-vs-`content` note](#built-in-ui-components).

**DOM contract.** Root `.px-panel-trigger[data-px-panel-id][data-px-panel-key]`; no own JS (wired by `panel.js`). `display: contents` so no layout box.

**Classes:** `px-panel-trigger`. No theming tokens.

---

## ConfirmDialog

Accessible `<dialog>` singleton that replaces `window.confirm`. Mount once in the layout; `px.confirm()` is available everywhere. **Assets:** `confirm-dialog.css`, `confirm-dialog.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `confirm_label` | `str` | `"Confirm"` | Default OK button text. |
| `cancel_label` | `str` | `"Cancel"` | Default cancel button text. |

```python
ConfirmDialog(id="app-confirm")
```

Intercepts every `hx-confirm="…"` automatically (via `htmx:confirm` event):

```html
<button hx-post="/delete/1"
        hx-confirm="Delete this item?"
        data-px-confirm-danger>Delete</button>
```

For non-htmx forms use `data-confirm="…"` on the `<form>`.

Override labels per-call:

```javascript
const ok = await px.confirm("Are you sure?", {
    okLabel: "Yes, delete",
    cancelLabel: "No",
    danger: true,
});
if (ok) { /* proceed */ }
```

**DOM contract.** Root `dialog.px-confirm-dialog[data-px-dialog="confirm"]` — singleton, matched by `document.querySelector`. `data-px-confirm-danger` on the htmx element → OK button gets `.px-confirm-dialog__ok--danger`. `data-px-confirm-ok` / `data-px-confirm-cancel` per-trigger label overrides.
API: `px.confirm(message, {okLabel?, cancelLabel?, danger?}) → Promise<boolean>`.
Falls back to `window.confirm` if no `ConfirmDialog` is mounted.

**Classes:** `px-confirm-dialog`, `px-confirm-dialog__card`, `px-confirm-dialog__message`, `px-confirm-dialog__actions`, `px-confirm-dialog__ok`, `px-confirm-dialog__ok--danger`, `px-confirm-dialog__cancel`. Theming: see [ConfirmDialog tokens](#confirmdialog-tokens).

---

## PromptDialog

Accessible `<dialog>` singleton that replaces `window.prompt`. Mount once in the layout; `px.prompt()` is available everywhere. **Assets:** `prompt-dialog.css`, `prompt-dialog.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `input_label` | `str` | `""` | Default label text above the input. |
| `submit_label` | `str` | `"OK"` | Submit button text. |
| `cancel_label` | `str` | `"Cancel"` | Cancel button text. |

```python
PromptDialog(id="app-prompt")
```

```javascript
const name = await px.prompt("Enter your name", {
    initial: "Alice",
    placeholder: "Full name",
    okLabel: "Save",
});
if (name !== null) { /* user submitted */ }
```

**DOM contract.** Root `dialog.px-prompt-dialog[data-px-dialog="prompt"]` — singleton, matched by `document.querySelector`. Input pre-focused and selected on open.
API: `px.prompt(title, {initial?, placeholder?, okLabel?, cancelLabel?}) → Promise<string | null>`.
Returns `null` on cancel/Escape/backdrop close. Falls back to `window.prompt` if no `PromptDialog` is mounted.

**Classes:** `px-prompt-dialog`, `px-prompt-dialog__card`, `px-prompt-dialog__label`, `px-prompt-dialog__input`, `px-prompt-dialog__actions`, `px-prompt-dialog__ok`, `px-prompt-dialog__cancel`. Theming: see [PromptDialog tokens](#promptdialog-tokens).

---

## ToastHost

HX-Trigger-driven toast container singleton. Mount once in the layout. **Assets:** `toast-host.css`, `toast-host.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `position` | literal | `"bottom-right"` | `top-right`, `top-left`, `bottom-right`, `bottom-left`. |
| `timeout` | `int` | `4000` | Default auto-dismiss ms; `0` disables. |
| `dismiss_label` | `str` | `"Dismiss"` | `aria-label` for dismiss buttons on individual toasts. |
| `event_name` | `str` | `"px:toast"` | Custom event name to listen for (wired on mount). |

```python
ToastHost(id="app-toasts", position="top-right")
```

Fire from a FastAPI route via `HX-Trigger`:

```python
import json

response.headers["HX-Trigger"] = json.dumps({"px:toast": {"message": "Saved.", "level": "success"}})
```

Or from JS:

```javascript
px.toast("Upload complete.", { level: "success", timeout: 3000 });
```

Toast `level` maps to `.px-toast--<level>`; supported values: `info`, `success`, `warning`, `error`.

**DOM contract.** Root `div.px-toast-host[data-px-toast-host]`. `data-event-name` sets the custom event; `data-timeout` sets the default dismiss timeout; `data-dismiss-label` sets dismiss button label.
Events (bubble from the host): `px:toasthost:show` (detail: `{level}`), `px:toasthost:hide`.
API: `px.toast(message, {level?, timeout?})`.
Individual toasts: `div.px-toast.px-toast--<level>` > `.px-toast__message` + `button.px-toast__dismiss`.

**Classes:** `px-toast-host`, `px-toast-host--top-right`, `--top-left`, `--bottom-right`, `--bottom-left`; `px-toast`, `px-toast--info`, `--success`, `--warning`, `--error`; `px-toast--hiding`; `px-toast__message`, `px-toast__dismiss`. Theming: see [ToastHost tokens](#toasthost-tokens).

---

## AvatarStack

Overlapping row of avatars with optional overflow count. **Assets:** `avatar-stack.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `avatars` | `list[str \| BaseComponent]` | `[]` | Avatar items (typically `Avatar` components or HTML strings). |
| `extra_count` | `int` | `0` | When `> 0`, renders a `+N` overflow chip. |
| `empty_label` | `str` | `""` | When no avatars and `empty_label` is set, renders a fallback label. |

```python
AvatarStack(
    id="team",
    avatars=[
        str(Avatar(id="a1", initials="AB", size="sm")),
        str(Avatar(id="a2", initials="CD", size="sm")),
    ],
    extra_count=3,
)
```

**DOM contract.** Root `.px-avatar-stack`; no JS API.

**Classes:** `px-avatar-stack`, `px-avatar-stack__more`, `px-avatar-stack__empty`. Theming: see [AvatarStack tokens](#avatarstack-tokens).

---

## PageLoader

Full-page navigation loader. Mount once at the top of the layout body. **Assets:** `page-loader.css`, `page-loader.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `nav_targets` | `str` | `"app-content"` | Comma-separated element ids whose htmx GET requests activate the loader. |
| `active_on_load` | `bool` | `True` | When `True`, renders with `.px-page-loader--active` (cold-load shimmer, removed on `DOMContentLoaded`). |
| `loading_label` | `str` | `"Loading"` | `aria-label` for the `role="status"` element. |

```python
PageLoader(id="page-loader", nav_targets="main-content,sidebar")
```

Add `data-px-loader` to any element to make its htmx requests activate the loader regardless of `nav_targets`:

```html
<a hx-get="/slow-page" hx-target="#main-content" data-px-loader>Go</a>
```

**DOM contract.** Root `div.px-page-loader[data-px-page-loader]` (state: `.px-page-loader--active`).
`data-nav-targets` — comma-separated ids; htmx GET requests targeting any of these activate the loader.
`data-px-loader` on any element marks its htmx requests as loader-tracked regardless of target.
Events (non-cancelable, bubble from the root): `px:page-loader:show`, `px:page-loader:hide`.
API: `px.loader.page.show()`, `px.loader.page.hide()`, `px.loader.page.reset()`, `px.loader.page.wrap(promise)`.

**Classes:** `px-page-loader`, `px-page-loader--active`, `px-page-loader__spinner`. Theming: see [PageLoader tokens](#pageloader-tokens).

---

## Example

```python
from pyjinhx.builtins import (
    AvatarStack,
    Badge,
    Breadcrumb,
    Card,
    ConfirmDialog,
    Drawer,
    Modal,
    Notification,
    PageLoader,
    Panel,
    PanelTrigger,
    TabGroup,
    ToastHost,
    Tooltip,
)

badge = Badge(id="status-badge", label="Beta", color="brand")
modal = Modal(id="info-modal", title="Hello", body="Content here.")
toast = Notification(id="welcome-toast", content="Saved.", corner="bottom-right", timeout=3000)
drawer = Drawer(id="filters", side="right", title="Filters", body="…")
tip = Tooltip(id="help-tip", trigger="?", tip="More detail", placement="top")
card = Card(id="summary", title="Summary", body="Details go here.")
crumb = Breadcrumb(id="crumb", items=[("App", "/"), ("Page", None)])
tabs = TabGroup(
    id="main-tabs",
    tabs={"A": "<p>First</p>", "B": "<p>Second</p>"},
)
main_panel = Panel(
    id="app-panels",
    panels={"chat": "<p>Chat UI</p>", "other": "<p>Other</p>"},
)
open_chat = PanelTrigger(
    id="open-chat", panel_id="app-panels", panel="chat", content="Chat"
)
confirm = ConfirmDialog(id="app-confirm")
toasts = ToastHost(id="app-toasts", position="bottom-right")
page_loader = PageLoader(id="page-loader")
avatar_stack = AvatarStack(id="team", avatars=[], extra_count=5)
```

---

## Theming tokens

Per-component `--px-*` custom properties and their default mappings. Override any token in your own CSS.

### Badge tokens

| Token | Default (maps to) |
| --- | --- |
| `--px-badge-font-size` | `var(--font-size-xs)` |
| `--px-badge-radius-sm` | `var(--radius-sm)` |
| `--px-badge-radius-md` | `var(--radius-md)` |
| `--px-badge-radius-full` | `var(--radius-full)` |
| `--px-badge-brand-bg` | `var(--brand-subtle)` |
| `--px-badge-brand-fg` | `var(--brand-muted)` |
| `--px-badge-brand-accent` | `var(--brand)` |
| `--px-badge-error-bg` | `var(--error-bg)` |
| `--px-badge-error-fg` | `var(--error)` |
| `--px-badge-error-border` | `var(--error-border)` |
| `--px-badge-neutral-bg` | `var(--surface-alt)` |
| `--px-badge-neutral-fg` | `var(--text)` |
| `--px-badge-neutral-border` | `var(--border)` |
| `--px-badge-muted-bg` | `var(--surface)` |
| `--px-badge-muted-fg` | `var(--text-muted)` |
| `--px-badge-muted-border` | `var(--border)` |

### Modal tokens

| Token | Default |
| --- | --- |
| `--px-modal-width` | `52rem` |
| `--px-modal-min-height` | `28rem` |
| `--px-modal-bg` | `var(--surface)` |
| `--px-modal-border` | `var(--border)` |
| `--px-modal-radius` | `var(--radius-lg)` |
| `--px-modal-shadow` | `var(--shadow-md)` |
| `--px-modal-header-bg` | `var(--surface-alt)` |
| `--px-modal-header-sep` | `var(--border)` |
| `--px-modal-footer-bg` | `var(--surface-alt)` |
| `--px-modal-footer-sep` | `var(--border)` |
| `--px-modal-title-color` | `var(--text)` |
| `--px-modal-close-color` | `var(--text-muted)` |
| `--px-modal-backdrop` | `rgb(0 0 0 / 0.6)` |
| `--px-modal-padding` | `1.5rem` |

Close control hover uses `var(--surface)`, `var(--text)`, `var(--radius-sm)`, `var(--transition)` from your theme.

### Notification tokens

| Token | Default |
| --- | --- |
| `--px-notification-width` | `22rem` |
| `--px-notification-gap` | `1.25rem` (viewport inset; used in slide animations) |
| `--px-notification-bg` | `var(--surface-alt)` |
| `--px-notification-border` | `var(--border)` |
| `--px-notification-radius` | `var(--radius-md)` |
| `--px-notification-shadow` | `var(--shadow-md)` |
| `--px-notification-padding` | `1rem 1rem 1rem 1.25rem` |
| `--px-notification-close-color` | `var(--text-muted)` |
| `--px-notification-z` | `500` |

Content uses `var(--font-size-sm)`, `var(--text)`; close hover uses `var(--surface)`, `var(--text)`, `var(--radius-sm)`, `var(--transition)`.

### Popover tokens

| Token | Default |
| --- | --- |
| `--px-popover-max-width` | `28ch` |
| `--px-popover-bg` | `var(--surface-alt)` |
| `--px-popover-border` | `var(--border)` |
| `--px-popover-radius` | `var(--radius-md)` |
| `--px-popover-shadow` | `var(--shadow-md)` |
| `--px-popover-padding` | `var(--space-3, 0.75rem) var(--space-4, 1rem)` |
| `--px-popover-z` | `300` |

### RegionLoader tokens

| Token | Default |
| --- | --- |
| `--px-region-loader-bg` | `rgb(0 0 0 / 0.55)` |
| `--px-region-loader-backdrop` | `blur(2px)` |
| `--px-region-loader-z` | `100` |
| `--px-region-loader-spinner-size` | `2.5rem` |
| `--px-region-loader-spinner-width` | `3px` |
| `--px-region-loader-spinner-color` | `var(--brand)` |
| `--px-region-loader-spinner-track` | `rgb(255 255 255 / 0.1)` |

### Tooltip tokens

| Token | Default |
| --- | --- |
| `--px-tooltip-gap` | `6px` |
| `--px-tooltip-bg` | `var(--surface-alt)` |
| `--px-tooltip-border` | `var(--border)` |
| `--px-tooltip-radius` | `var(--radius-sm)` |
| `--px-tooltip-shadow` | `var(--shadow-md)` |
| `--px-tooltip-padding` | `0.35rem 0.5rem` |
| `--px-tooltip-max-width` | `20ch` |
| `--px-tooltip-fg` | `var(--text)` |
| `--px-tooltip-font-size` | `var(--font-size-xs)` |
| `--px-tooltip-z` | `400` |

### Alert tokens

| Token | Default |
| --- | --- |
| `--px-alert-radius` | `var(--radius-md)` |
| `--px-alert-padding` | `0.875rem 1rem` |
| `--px-alert-border` | `var(--border)` |
| `--px-alert-shadow` | `var(--shadow-md)` |
| `--px-alert-title-size` | `var(--font-size-sm)` |
| `--px-alert-body-size` | `var(--font-size-sm)` |
| `--px-alert-dismiss-color` | `var(--text-muted)` |

### Dropdown tokens

| Token | Default |
| --- | --- |
| `--px-dropdown-menu-bg` | `var(--surface-alt)` |
| `--px-dropdown-menu-border` | `var(--border)` |
| `--px-dropdown-menu-radius` | `var(--radius-md)` |
| `--px-dropdown-menu-shadow` | `var(--shadow-md)` |
| `--px-dropdown-menu-padding` | `0.35rem 0` |
| `--px-dropdown-menu-min-w` | `10rem` |
| `--px-dropdown-menu-max-h` | `min(70dvh, 24rem)` |
| `--px-dropdown-z` | `350` |

### Drawer tokens

| Token | Default |
| --- | --- |
| `--px-drawer-width` | `min(24rem, 100vw)` |
| `--px-drawer-height-bottom` | `min(50dvh, 28rem)` |
| `--px-drawer-bg` | `var(--surface)` |
| `--px-drawer-border` | `var(--border)` |
| `--px-drawer-shadow` | `var(--shadow-md)` |
| `--px-drawer-backdrop` | `rgb(0 0 0 / 0.45)` |
| `--px-drawer-header-bg` | `var(--surface-alt)` |
| `--px-drawer-header-sep` | `var(--border)` |
| `--px-drawer-footer-bg` | `var(--surface-alt)` |
| `--px-drawer-footer-sep` | `var(--border)` |
| `--px-drawer-padding` | `1rem` |
| `--px-drawer-z` | `250` |

### Progress tokens

| Token | Default |
| --- | --- |
| `--px-progress-height` | `0.5rem` |
| `--px-progress-radius` | `var(--radius-full)` |
| `--px-progress-track` | `var(--surface-alt)` |
| `--px-progress-fill` | `var(--brand)` |
| `--px-progress-indeterminate-speed` | `1.2s` |

### Skeleton tokens

| Token | Default |
| --- | --- |
| `--px-skeleton-bg` | `var(--surface-alt)` |
| `--px-skeleton-shine` | `color-mix(in srgb, var(--text) 8%, var(--surface-alt))` |
| `--px-skeleton-line-height` | `0.65rem` |
| `--px-skeleton-line-gap` | `0.5rem` |
| `--px-skeleton-circle-size` | `2.5rem` |
| `--px-skeleton-rect-height` | `6rem` |
| `--px-skeleton-rect-radius` | `var(--radius-md)` |
| `--px-skeleton-duration` | `1.2s` |

### EmptyState tokens

| Token | Default |
| --- | --- |
| `--px-empty-state-padding` | `2rem 1.5rem` |
| `--px-empty-state-max-width` | `28rem` |
| `--px-empty-state-title-size` | `var(--font-size-md)` |
| `--px-empty-state-desc-size` | `var(--font-size-sm)` |
| `--px-empty-state-title-color` | `var(--text)` |
| `--px-empty-state-desc-color` | `var(--text-muted)` |
| `--px-empty-state-gap` | `0.5rem` |
| `--px-empty-state-actions-gap` | `0.5rem` |

### Divider tokens

| Token | Default |
| --- | --- |
| `--px-divider-color` | `var(--border)` |
| `--px-divider-thickness` | `1px` |
| `--px-divider-gap` | `0.75rem` |
| `--px-divider-label-color` | `var(--text-muted)` |
| `--px-divider-label-size` | `var(--font-size-sm)` |

### Spinner tokens

| Token | Default |
| --- | --- |
| `--px-spinner-sm` | `1.25rem` |
| `--px-spinner-md` | `2rem` |
| `--px-spinner-lg` | `2.75rem` |
| `--px-spinner-track` | `color-mix(in srgb, var(--text-muted) 35%, transparent)` |
| `--px-spinner-accent` | `var(--brand)` |

### Avatar tokens

| Token | Default |
| --- | --- |
| `--px-avatar-sm` | `2rem` |
| `--px-avatar-md` | `2.5rem` |
| `--px-avatar-lg` | `3.25rem` |
| `--px-avatar-bg` | `var(--surface-alt)` |
| `--px-avatar-fg` | `var(--text-muted)` |
| `--px-avatar-border` | `var(--border)` |

### Card tokens

| Token | Default |
| --- | --- |
| `--px-card-bg` | `var(--surface-alt)` |
| `--px-card-border` | `var(--border)` |
| `--px-card-radius` | `var(--radius-md)` |
| `--px-card-title-color` | `var(--text)` |
| `--px-card-padding` | `var(--space-4, 1rem)` |

### Breadcrumb tokens

| Token | Default |
| --- | --- |
| `--px-breadcrumb-sep` | `"/"` |
| `--px-breadcrumb-link-color` | `var(--brand)` |
| `--px-breadcrumb-current-color` | `var(--text)` |

### TabGroup tokens

| Token | Default |
| --- | --- |
| `--px-tab-group-border` | `var(--border)` |
| `--px-tab-group-bg` | `var(--surface-alt)` |
| `--px-tab-group-tab-active-fg` | `var(--text)` |
| `--px-tab-group-tab-active-bg` | `color-mix(in srgb, var(--surface) 55%, var(--surface-alt))` |
| `--px-tab-group-tab-active-border` | `var(--brand)` |
| `--px-tab-group-panel-bg` | `var(--surface)` |

### ConfirmDialog tokens

| Token | Default |
| --- | --- |
| `--px-confirm-dialog-bg` | `var(--surface)` |
| `--px-confirm-dialog-border` | `var(--border)` |
| `--px-confirm-dialog-radius` | `var(--radius-md)` |
| `--px-confirm-dialog-shadow` | `var(--shadow-md)` |
| `--px-confirm-dialog-backdrop` | `rgb(0 0 0 / 0.5)` |
| `--px-confirm-dialog-danger` | `#b3261e` |

### PromptDialog tokens

| Token | Default |
| --- | --- |
| `--px-prompt-dialog-bg` | `var(--surface)` |
| `--px-prompt-dialog-border` | `var(--border)` |
| `--px-prompt-dialog-radius` | `var(--radius-md)` |
| `--px-prompt-dialog-shadow` | `var(--shadow-md)` |
| `--px-prompt-dialog-backdrop` | `rgb(0 0 0 / 0.5)` |

### ToastHost tokens

| Token | Default |
| --- | --- |
| `--px-toast-bg` | `var(--surface)` |
| `--px-toast-border` | `var(--border)` |
| `--px-toast-radius` | `var(--radius-md)` |
| `--px-toast-shadow` | `var(--shadow-md)` |
| `--px-toast-gap` | `0.5rem` |
| `--px-toast-z` | `1000` |
| `--px-toast-info` | `var(--brand, #5c8fa8)` |
| `--px-toast-success` | `#3e7d4f` |
| `--px-toast-warning` | `#b07415` |
| `--px-toast-error` | `#b3261e` |

### AvatarStack tokens

| Token | Default |
| --- | --- |
| `--px-avatar-stack-overlap` | `-0.5rem` |
| `--px-avatar-stack-ring` | `var(--surface)` |

### PageLoader tokens

| Token | Default |
| --- | --- |
| `--px-page-loader-backdrop` | `rgb(0 0 0 / 0.15)` |
| `--px-page-loader-z` | `9999` |
| `--px-page-loader-size` | `2rem` |
