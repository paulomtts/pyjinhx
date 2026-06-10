# Built-in UI components

Optional package **`pyjinhx.builtins`** registers twenty-one [`BaseComponent`](../api/base-component.md) subclasses. Import:

```python
from pyjinhx.builtins import (
    Alert,
    Avatar,
    Badge,
    Breadcrumb,
    Card,
    Divider,
    Dropdown,
    Drawer,
    EmptyState,
    LazyPanel,
    LoadingOverlay,
    Modal,
    Notification,
    Popover,
    Progress,
    Panel,
    PanelTrigger,
    Skeleton,
    Spinner,
    TabGroup,
    Tooltip,
)
```

`__all__` matches that set of twenty-one names.

**Conventions:** Markup classes use the **`px-`** prefix; overrides use **`--px-`** custom properties. Builtin CSS also references **theme variables** (`--surface`, `--border`, `--text`, `--radius-md`, `--shadow-md`, `--transition`, `--brand`, …)—define those in your global CSS or map them to your design system.

**Template discovery:** Builtins ship inside `site-packages`, not under your app's Jinja loader root, so PascalCase tags do **not** auto-discover them — `<Tooltip/>` raises a `FileNotFoundError` unless the class was imported once at startup (`import pyjinhx.builtins` or any of the imports above), which registers it. For registered builtin classes, the renderer **falls back** to adjacent package templates: each component's Jinja template lives next to its Python source in `pyjinhx/builtins/ui/<component>/` (e.g. `pyjinhx/builtins/ui/modal/modal.html`).

**Inherited fields:** Every component inherits **`id`** (required), **`js`** / **`css`** (extra asset paths), **`render()`**, and **`__html__()`** from [`BaseComponent`](../api/base-component.md). Because `id` is universal it is omitted from the per-component props tables below. `extra="allow"` lets you pass additional kwargs into the Jinja context.

**Theming:** Per-component `--px-*` tokens are collected in the [Theming tokens](#theming-tokens) appendix. Each component section points there.

**CSS-only components** (no bundled script): Badge, Tooltip, Progress, Skeleton, EmptyState, Divider, Spinner, Avatar, Card, Breadcrumb. (Tooltip and Popover ship CSS plus an IIFE that exports no globals.) LazyPanel ships no assets at all.

**Children-vs-`content` tag gotcha (children-mapping components):** Several components map children to a single attribute (e.g. Tooltip `tip`, Popover `card_content`, Notification `content`, PanelTrigger `content`). If you use `Renderer.render()` with PascalCase tags, do **not** supply both child text and the corresponding attribute on the same tag—use body text as the child *or* the attribute, not both.

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
| `class_name` | `str` | `""` | Extra classes after the `px-badge*` classes. |

**Classes:** `px-badge`; color modifiers `px-badge--brand`, `--error`, `--neutral`, `--muted`; shape `px-badge--square`, `--sm`, `--md`, `--full`. Theming: see [appendix](#badge-1).

---

## Modal

Native `<dialog>`. **Assets:** `modal.css`, `modal.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `title` | `str \| BaseComponent` | `""` | Default header title when `header` is empty. |
| `header` | `str \| BaseComponent` | `""` | If set, replaces the built-in title row. |
| `body` | `str \| BaseComponent` | `""` | Main content; wrapper id `{{ id }}-body`. |
| `footer` | `str \| BaseComponent` | `""` | If non-empty, renders `<footer class="px-modal__footer">`. |

Globals from **`modal.js`** (injected with the component):

| Function | Description |
| --- | --- |
| `openModal(id)` | `document.getElementById(id).showModal()` if present. |
| `closeModal(id)` | Adds `px-modal--closing`, on `animationend` removes it and calls `dialog.close()`. |

Backdrop click closes the dialog (see [intro note](#built-in-ui-components)).

**Classes:** `px-modal`; closing state `px-modal--closing`; `px-modal__box`, `__header`, `__title`, `__close`, `__body`, `__footer`. Theming: see [appendix](#modal-1).

---

## Notification

Fixed-position toast. **Assets:** `notification.css`, `notification.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Message body. |
| `corner` | literal | `"top-right"` | `top-right`, `top-left`, `bottom-right`, `bottom-left`. |
| `timeout` | `int` | `5000` | Auto-dismiss ms; `0` disables. Rendered as `data-timeout`. |

Globals from **`notification.js`**:

| Function | Description |
| --- | --- |
| `showNotification(id)` | Clears `px-notification--hiding`, adds `px-notification--visible`. Reads `data-timeout`; if numeric `> 0`, schedules `hideNotification(id)`. |
| `hideNotification(id)` | If visible, adds `px-notification--hiding`; on `animationend` removes `visible` / `hiding`. |

**Classes:** `px-notification`; placement `px-notification--top-right`, `--top-left`, `--bottom-right`, `--bottom-left`; JS state `px-notification--visible`, `px-notification--hiding`; `px-notification__content`, `px-notification__close`. Theming: see [appendix](#notification-1).

---

## Popover

Hover trigger + floating card. **Assets:** `popover.css`, `popover.js` (IIFE, no globals).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Trigger label (`px-popover-trigger__body`). |
| `card_content` | `str \| BaseComponent` | `""` | Panel body (`px-popover-card`). |
| `position` | literal | `"anchor"` | `anchor` (below trigger) or `follow` (pointer). → `data-popover-position`. |
| `backdrop` | `bool` | `False` | When `True`, emits `data-popover-backdrop` on the trigger (dim layer + lifted z-index). |

**Runtime behavior:** Mouse over the trigger opens the card; leaving the trigger (and its descendants) starts a short delayed hide. With **`data-popover-backdrop`** on the trigger (set `backdrop=True`, or add the attribute in custom markup), the script shows a full-screen dim layer, lifts the trigger z-index, and injects `#px-popover-backdrop` if needed.

No exported functions. Behavior is driven by:

| Mechanism | Role |
| --- | --- |
| `.px-popover-trigger` / `.px-popover-card` | Discovery and visibility (`px-popover-card--visible`). |
| `data-popover-position` | `anchor` or `follow` (pointer tracking). |
| `data-popover-backdrop` | If present (any value), backdrop + trigger lift. |
| `#px-popover-backdrop` | Shared element; class `px-popover-backdrop`, state `px-popover-backdrop--visible`. |

**Classes:** `px-popover-trigger`, `px-popover-trigger__body`, `px-popover-card`, `px-popover-card--visible`, `px-popover-backdrop`, `px-popover-backdrop--visible`. Backdrop fill is fixed **`rgba(0, 0, 0, 0.35)`** in CSS (not a token); JS sets `z-index: calc(var(--px-popover-z) + 1)` on the trigger when the backdrop is active. Theming: see [appendix](#popover-1).

---

## LoadingOverlay

In-place loading veil over a positioned ancestor. **Assets:** `loading-overlay.css`, `loading-overlay.js`.

This component declares no extra fields beyond the inherited `id`.

**Layout:** Overlay is `position: absolute; inset: 0`. Parent must be **`position: relative`** (or any non-`static` value) so coverage is correct.

Globals from **`loading-overlay.js`**. Show/hide are **reference-counted per `id`**, so overlapping async operations are safe: the overlay stays visible until every `show` is matched by a `hide`.

| Function | Description |
| --- | --- |
| `showLoadingOverlay(id)` | Increments the count; on 0 → 1 removes `px-loading-overlay--hiding` and adds `px-loading-overlay--visible`. |
| `hideLoadingOverlay(id)` | Decrements the count (floor 0); on 1 → 0 adds `px-loading-overlay--hiding`, then `animationend` clears both state classes. |
| `resetLoadingOverlay(id)` | Zeroes the count and clears both state classes immediately (no animation) — escape hatch for stranded counts, e.g. a missed `hide` on an error path or htmx history back-navigation. |

**Classes:** `px-loading-overlay`; state `px-loading-overlay--visible`, `px-loading-overlay--hiding`; `px-loading-overlay__spinner`. Spinner ring uses **`var(--radius-full)`** from your theme. Theming: see [appendix](#loadingoverlay-1).

---

## Tooltip

Compact focus/hover hint. **Assets:** `tooltip.css`, `tooltip.js` (IIFE).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `trigger` | `str \| BaseComponent` | `""` | Focusable trigger (`px-tooltip__trigger`, `tabindex="0"`). |
| `tip` | `str \| BaseComponent` | `""` | `role="tooltip"` body. |
| `placement` | literal | `"top"` | `top`, `bottom`, `start`, `end` → `data-px-tooltip-placement`. |

Maps children to `tip`; see the [children-vs-`content` note](#built-in-ui-components). Theming: see [appendix](#tooltip-1).

---

## Alert

Inline status banner. **Assets:** `alert.css`, `alert.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `variant` | literal | `"info"` | `info`, `success`, `warning`, `error` → `px-alert--{variant}`. |
| `title` | `str` | `""` | Optional heading. |
| `body` | `str \| BaseComponent` | `""` | Main copy. |
| `dismissible` | `bool` | `False` | When true, renders dismiss control calling `dismissPxAlert`. |

| Function | Description |
| --- | --- |
| `dismissPxAlert(id)` | Adds `px-alert--dismissed` (hides via `display: none`). |

Variants use `color-mix` with `--brand`, `--success`, `--warning`, or `--error` / `--error-bg` / `--error-border` where applicable. Theming: see [appendix](#alert-1).

---

## Dropdown

Button + anchored panel. **Assets:** `dropdown.css`, `dropdown.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `trigger` | `str \| BaseComponent` | `""` | Button label. |
| `menu` | `str \| BaseComponent` | `""` | Panel HTML (e.g. links or custom markup). |

Trigger id is `{{ id }}-trigger`, menu is `{{ id }}-menu`.

| Function | Description |
| --- | --- |
| `togglePxDropdown(id)` | Toggles `hidden` on the menu and `aria-expanded` on the trigger. |
| `closePxDropdown(id)` | Closes the menu. |

**Listeners:** `document` `click` closes any open menu whose root does not contain the event target. `keydown` `Escape` closes all open menus. Theming: see [appendix](#dropdown-1).

---

## Drawer

`<dialog>` sheet from an edge. **Assets:** `drawer.css`, `drawer.js`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `side` | literal | `"right"` | `left`, `right`, or `bottom` → `px-drawer--{side}`. |
| `title` | `str \| BaseComponent` | `""` | Header title. |
| `body` | `str \| BaseComponent` | `""` | Scrollable body. |
| `footer` | `str \| BaseComponent` | `""` | Optional footer strip. |

| Function | Description |
| --- | --- |
| `openPxDrawer(id)` | `showModal()` on the dialog. |
| `closePxDrawer(id)` | Adds `px-drawer--closing`; on `animationend`, removes it and `dialog.close()`. |

Backdrop click closes the dialog (see [intro note](#built-in-ui-components)). Theming: see [appendix](#drawer-1).

---

## Progress

Determinate or indeterminate meter. **Assets:** `progress.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `value` | `float \| None` | `None` | Omit or `None` for indeterminate `<progress>`. |
| `max` | `float` | `100` | Passed to `<progress max="…">`. |
| `label` | `str` | `""` | Optional `px-progress__label`; wires `aria-labelledby` when set. |

Theming: see [appendix](#progress-1).

---

## Skeleton

Placeholder shimmer blocks. **Assets:** `skeleton.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `variant` | literal | `"text"` | `text` (stacked lines), `circle`, or `rect`. |
| `lines` | `int` | `3` | For `text`, count of `px-skeleton__line` rows. |
| `class_name` | `str` | `""` | Extra classes on the root. |

Theming: see [appendix](#skeleton-1).

---

## EmptyState

Centered empty view. **Assets:** `empty-state.css` only (template file **`empty-state.html`** next to `empty_state.py`).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `image` | `str \| BaseComponent` | `""` | Optional slot above the heading (e.g. illustration markup). |
| `title` | `str \| BaseComponent` | `""` | Heading. |
| `description` | `str \| BaseComponent` | `""` | Supporting text. |
| `action` | `str \| BaseComponent` | `""` | Optional slot (e.g. button markup). |
| `actions` | `list[str \| BaseComponent]` | `[]` | Optional flex row of slots (e.g. suggestion chips); renders after `action` when both are set. |

Theming: see [appendix](#emptystate-1).

---

## LazyPanel

HTMX lazy-load wrapper: a single `div` that fetches `url` on `trigger` and swaps itself with the response. **Assets:** none (template file **`lazy-panel.html`** next to `lazy_panel.py`).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `url` | `str` | required | Endpoint for the deferred content (`hx-get`). |
| `trigger` | `str` | `"revealed"` | `hx-trigger` value; the default fires when scrolled into view. |
| `swap` | `str` | `"outerHTML"` | `hx-swap` strategy; the default replaces the wrapper itself. |
| `content` | `str \| BaseComponent` | `""` | Optional placeholder shown until the fetch lands (e.g. a [`Skeleton`](#skeleton)). |

```python
LazyPanel(id="comments", url="/posts/42/comments", content=Skeleton(id="comments-skel"))
```

**Classes:** `px-lazy-panel` (unstyled hook). No theming tokens.

---

## Divider

Separator line. **Assets:** `divider.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `orientation` | literal | `"horizontal"` | `horizontal` (default `hr`) or `vertical` (bar). |
| `label` | `str` | `""` | If set with horizontal orientation, flex row with label between lines. |
| `class_name` | `str` | `""` | Extra classes on the root. |

**Classes:** `px-divider--horizontal`, `px-divider--vertical`, `px-divider--labeled`, `px-divider__line`, `px-divider__label`. Theming: see [appendix](#divider-1).

---

## Spinner

Inline loading indicator. **Assets:** `spinner.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `size` | literal | `"md"` | `sm`, `md`, or `lg`. |
| `label` | `str` | `"Loading"` | Visually hidden; exposed to assistive tech. |

**Classes:** `px-spinner`, `px-spinner--sm|md|lg`, `px-spinner__ring`, `px-spinner__label` (screen-reader-only). Theming: see [appendix](#spinner-1).

---

## Avatar

Image or initials in a circle. **Assets:** `avatar.css` only (template **`avatar.html`**).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `src` | `str` | `""` | Image URL; when empty, initials fallback is shown. |
| `alt` | `str` | `""` | `img` alt text; also used as `title` on initials. |
| `initials` | `str` | `""` | Up to two characters (trimmed/capped in validation). |
| `size` | literal | `"md"` | `sm`, `md`, or `lg`. |
| `class_name` | `str` | `""` | Extra classes on the root. |

**Classes:** `px-avatar`, `px-avatar--sm|md|lg`, `px-avatar__img`, `px-avatar__initials`. Theming: see [appendix](#avatar-1).

---

## Card

Grouped content with optional header and footer. **Assets:** `card.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `title` | `str \| BaseComponent` | `""` | Default header title (ignored if `header` is set). |
| `header` | `str \| BaseComponent` | `""` | Custom header slot; replaces `title` block when set. |
| `body` | `str \| BaseComponent` | `""` | Main content. |
| `footer` | `str \| BaseComponent` | `""` | Optional footer. |

**Classes:** `px-card`, `px-card__header`, `px-card__title`, `px-card__body`, `px-card__footer`. Theming: see [appendix](#card-1).

---

## Breadcrumb

Ordered trail of links. **Assets:** `breadcrumb.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `items` | `list[tuple[str, str \| None]]` | `[]` | `(label, href)` left to right; `href` `None` marks the current page. |

`items` may also be passed as a **JSON array** string (e.g. from PascalCase tags): `[["Home","/"],["Here",null]]`.

**Classes:** `px-breadcrumb`, `px-breadcrumb__list`, `px-breadcrumb__item`, `px-breadcrumb__link`, `px-breadcrumb__current`. Separators via `::after` on items except the last. Theming: see [appendix](#breadcrumb-1).

---

## TabGroup

Tab buttons and panels. **Assets:** `tab-group.css`, **`tab-group.js`** (kebab-case filenames so the renderer's JS/CSS collector finds them; see `LoadingOverlay` → `loading-overlay.*`).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `tabs` | `dict[str, str \| BaseComponent]` | `{}` | **Insertion order** is tab order; keys are labels, values are panel bodies. |

`tabs` may also be a **JSON object** string from markup tags (values are HTML strings).

**`tab-group.js`:** `click` delegation on `.px-tab-group__tab` updates `aria-selected`, `tabindex`, and `hidden` on sibling panels within the same `.px-tab-group`.

**Classes:** `px-tab-group`, `px-tab-group__list`, `px-tab-group__tab`, `px-tab-group__panel`. Theming: see [appendix](#tabgroup-1).

---

## Panel

Host for **distributed** tab-like switching: all bodies render here; controls are separate [`PanelTrigger`](#paneltrigger) components. **Unstyled** aside from `hidden` panels. **Assets:** `panel.css`, **`panel.js`**.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `panels` | `dict[str, str \| BaseComponent]` | `{}` | **Insertion order** sets the initially visible slot (first is shown). Keys must match `[a-zA-Z0-9_-]+`. |

`panels` may be a **JSON object** string from PascalCase tags. Keys are used in HTML `id` attributes and `data-px-panel-key`. Slot element ids are `{{ id }}-panel-{{ key }}`. The `id` must match `PanelTrigger.panel_id`.

**`panel.js`:** `click` on `.px-panel-trigger` shows the matching `.px-panel__panel` inside the host `getElementById(panel_id)`, hides others, syncs `aria-selected` / `tabIndex` on **all** triggers for that host. **`pxPanelInit`** runs on `DOMContentLoaded`, `htmx:afterSwap`, and `htmx:afterSettle` so swapped fragments pick up correct ARIA after partial updates.

**Classes:** `px-panel`, `px-panel__panel`. No theme tokens; minimal rules for `[hidden]` panels.

---

## PanelTrigger

Invisible wrapper that wires clicks to a [`Panel`](#panel) slot (place it anywhere; put your own links, buttons, or styled markup in `content`, same pattern as [`Popover`](#popover) / [`Notification`](#notification)). **Assets:** `panel-trigger.css`. See the [`panel.js` loading note](#built-in-ui-components)—render a `Panel` on the same page so the script is included.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `panel_id` | `str` | (required) | Must equal the target `Panel.id`. |
| `panel` | `str` | (required) | Key matching a key in `Panel.panels`; `[a-zA-Z0-9_-]+`. |
| `content` | `str \| BaseComponent` | `""` | Inner HTML / nested components (your visible control). |

Maps children to `content`; see the [children-vs-`content` note](#built-in-ui-components).

**`panel-trigger.css`:** `.px-panel-trigger { display: contents; }` so the wrapper does not create a layout box. Override in your app (e.g. `display: block`) if you need a real box.

---

## Example

```python
from pyjinhx.builtins import (
    Badge,
    Breadcrumb,
    Card,
    Drawer,
    Modal,
    Notification,
    Panel,
    PanelTrigger,
    TabGroup,
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
```

---

## Theming tokens

Per-component `--px-*` custom properties and their default mappings. Override any token in your own CSS. Components not listed here (Panel, PanelTrigger, Tooltip's IIFE behavior, etc.) expose no tokens or are noted inline above.

### Badge

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

### Modal

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

### Notification

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

### Popover

| Token | Default |
| --- | --- |
| `--px-popover-max-width` | `28ch` |
| `--px-popover-bg` | `var(--surface-alt)` |
| `--px-popover-border` | `var(--border)` |
| `--px-popover-radius` | `var(--radius-md)` |
| `--px-popover-shadow` | `var(--shadow-md)` |
| `--px-popover-padding` | `var(--space-3, 0.75rem) var(--space-4, 1rem)` |
| `--px-popover-z` | `300` |

### LoadingOverlay

| Token | Default |
| --- | --- |
| `--px-loading-overlay-bg` | `rgb(0 0 0 / 0.55)` |
| `--px-loading-overlay-backdrop` | `blur(2px)` |
| `--px-loading-overlay-z` | `100` |
| `--px-loading-overlay-spinner-size` | `2.5rem` |
| `--px-loading-overlay-spinner-width` | `3px` |
| `--px-loading-overlay-spinner-color` | `var(--brand)` |
| `--px-loading-overlay-spinner-track` | `rgb(255 255 255 / 0.1)` |

### Tooltip

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

### Alert

| Token | Default |
| --- | --- |
| `--px-alert-radius` | `var(--radius-md)` |
| `--px-alert-padding` | `0.875rem 1rem` |
| `--px-alert-border` | `var(--border)` |
| `--px-alert-shadow` | `var(--shadow-md)` |
| `--px-alert-title-size` | `var(--font-size-sm)` |
| `--px-alert-body-size` | `var(--font-size-sm)` |
| `--px-alert-dismiss-color` | `var(--text-muted)` |

### Dropdown

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

### Drawer

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

### Progress

| Token | Default |
| --- | --- |
| `--px-progress-height` | `0.5rem` |
| `--px-progress-radius` | `var(--radius-full)` |
| `--px-progress-track` | `var(--surface-alt)` |
| `--px-progress-fill` | `var(--brand)` |
| `--px-progress-indeterminate-speed` | `1.2s` |

### Skeleton

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

### EmptyState

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

### Divider

| Token | Default |
| --- | --- |
| `--px-divider-color` | `var(--border)` |
| `--px-divider-thickness` | `1px` |
| `--px-divider-gap` | `0.75rem` |
| `--px-divider-label-color` | `var(--text-muted)` |
| `--px-divider-label-size` | `var(--font-size-sm)` |

### Spinner

| Token | Default |
| --- | --- |
| `--px-spinner-sm` | `1.25rem` |
| `--px-spinner-md` | `2rem` |
| `--px-spinner-lg` | `2.75rem` |
| `--px-spinner-track` | `color-mix(in srgb, var(--text-muted) 35%, transparent)` |
| `--px-spinner-accent` | `var(--brand)` |

### Avatar

| Token | Default |
| --- | --- |
| `--px-avatar-sm` | `2rem` |
| `--px-avatar-md` | `2.5rem` |
| `--px-avatar-lg` | `3.25rem` |
| `--px-avatar-bg` | `var(--surface-alt)` |
| `--px-avatar-fg` | `var(--text-muted)` |
| `--px-avatar-border` | `var(--border)` |

### Card

| Token | Default |
| --- | --- |
| `--px-card-bg` | `var(--surface-alt)` |
| `--px-card-border` | `var(--border)` |
| `--px-card-radius` | `var(--radius-md)` |
| `--px-card-title-color` | `var(--text)` |
| `--px-card-padding` | `var(--space-4, 1rem)` |

### Breadcrumb

| Token | Default |
| --- | --- |
| `--px-breadcrumb-sep` | `"/"` |
| `--px-breadcrumb-link-color` | `var(--brand)` |
| `--px-breadcrumb-current-color` | `var(--text)` |

### TabGroup

| Token | Default |
| --- | --- |
| `--px-tab-group-border` | `var(--border)` |
| `--px-tab-group-bg` | `var(--surface-alt)` |
| `--px-tab-group-tab-active-fg` | `var(--text)` |
| `--px-tab-group-tab-active-bg` | `color-mix(in srgb, var(--surface) 55%, var(--surface-alt))` |
| `--px-tab-group-tab-active-border` | `var(--brand)` |
| `--px-tab-group-panel-bg` | `var(--surface)` |
</content>
</invoke>
