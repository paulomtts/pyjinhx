# Built-in UI components

Optional package **`pyjinhx.builtins`** registers twenty [`BaseComponent`](../api/base-component.md) subclasses. Import:

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
    LoadingOverlay,
    Modal,
    Notification,
    Popover,
    Progress,
    Region,
    RegionTrigger,
    Skeleton,
    Spinner,
    TabGroup,
    Tooltip,
)
```

`__all__` matches that set of twenty names.

**Conventions:** Markup classes use the **`px-`** prefix; overrides use **`--px-`** custom properties. Builtin CSS also references **theme variables** (`--surface`, `--border`, `--text`, `--radius-md`, `--shadow-md`, `--transition`, `--brand`, …)—define those in your global CSS or map them to your design system.

**Template discovery:** Builtins ship inside `site-packages`. If your Jinja loader only covers your app tree, the renderer **falls back** to adjacent package templates for `pyjinhx.builtins` classes.

Every component below inherits **`id`** (required), **`js`** / **`css`** (extra asset paths), **`render()`**, and **`__html__()`** from [`BaseComponent`](../api/base-component.md). `extra="allow"` lets you pass additional kwargs into the Jinja context.

---

## Badge

Small status label. **Assets:** `badge.css` only.

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Element id. |
| `label` | `str` | `""` | Inner text. |
| `color` | literal | `"neutral"` | `brand`, `error`, `neutral`, `muted` → `px-badge--{color}`. |
| `shape` | literal | `"md"` | `square`, `sm`, `md`, `full` → `px-badge--{shape}`. |
| `class_name` | `str` | `""` | Extra classes after the `px-badge*` classes. |


### HTML

??? abstract "HTML (Jinja template)"

    ```html
    <span class="px-badge px-badge--{{ color }} px-badge--{{ shape }}{% if class_name %} {{ class_name }}{% endif %}">{{ label }}</span>
    ```

### JavaScript

No bundled script.

### Style

**Classes:** `px-badge`; color modifiers `px-badge--brand`, `--error`, `--neutral`, `--muted`; shape `px-badge--square`, `--sm`, `--md`, `--full`.

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

---

## Modal

Native `<dialog>`. **Assets:** `modal.css`, `modal.js`.

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | `<dialog id>`; used by `openModal` / `closeModal`. |
| `title` | `str \| BaseComponent` | `""` | Default header title when `header` is empty. |
| `header` | `str \| BaseComponent` | `""` | If set, replaces the built-in title row. |
| `body` | `str \| BaseComponent` | `""` | Main content; wrapper id `{{ id }}-body`. |
| `footer` | `str \| BaseComponent` | `""` | If non-empty, renders `<footer class="px-modal__footer">`. |


### HTML

??? abstract "HTML (Jinja template)"

    ```html
    <dialog class="px-modal" id="{{ id }}">
        <div class="px-modal__box">
            <header class="px-modal__header">
                {% if header %}
                {{ header }}
                {% else %}
                <span class="px-modal__title">{{ title }}</span>
                {% endif %}
                <button class="px-modal__close"
                        onclick="closeModal('{{ id }}')"
                        aria-label="Close">&#x2715;</button>
            </header>

            <div class="px-modal__body" id="{{ id }}-body">{{ body }}</div>

            {% if footer %}
            <footer class="px-modal__footer">{{ footer }}</footer>
            {% endif %}
        </div>
    </dialog>
    ```

### JavaScript

Globals from **`modal.js`** (injected with the component):

| Function | Description |
| --- | --- |
| `openModal(id)` | `document.getElementById(id).showModal()` if present. |
| `closeModal(id)` | Adds `px-modal--closing`, on `animationend` removes it and calls `dialog.close()`. |

**Document listener:** `click` on `event.target.tagName === 'DIALOG'` runs `closeModal(event.target.id)` (backdrop click). Any native `<dialog>` root clicked directly is affected—use unique ids and avoid multiple stacked modals unless you adjust this.

### Style

**Classes:** `px-modal`; closing state `px-modal--closing`; `px-modal__box`, `__header`, `__title`, `__close`, `__body`, `__footer`. Close control hover uses `var(--surface)`, `var(--text)`, `var(--radius-sm)`, `var(--transition)` from your theme.

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

---

## Notification

Fixed-position toast. **Assets:** `notification.css`, `notification.js`.

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root id for `showNotification` / `hideNotification`. |
| `content` | `str \| BaseComponent` | `""` | Message body. |
| `corner` | literal | `"top-right"` | `top-right`, `top-left`, `bottom-right`, `bottom-left`. |
| `timeout` | `int` | `5000` | Auto-dismiss ms; `0` disables. Rendered as `data-timeout`. |


### HTML

??? abstract "HTML (Jinja template)"

    ```html
    <div class="px-notification px-notification--{{ corner }}"
         id="{{ id }}"
         data-timeout="{{ timeout }}"
         role="status"
         aria-live="polite">
        <div class="px-notification__content">{{ content }}</div>
        <button class="px-notification__close"
                onclick="hideNotification('{{ id }}')"
                aria-label="Dismiss">&#x2715;</button>
    </div>
    ```

### JavaScript

Globals from **`notification.js`**:

| Function | Description |
| --- | --- |
| `showNotification(id)` | Clears `px-notification--hiding`, adds `px-notification--visible`. Reads `data-timeout`; if numeric `> 0`, schedules `hideNotification(id)`. |
| `hideNotification(id)` | If visible, adds `px-notification--hiding`; on `animationend` removes `visible` / `hiding`. |

### Style

**Classes:** `px-notification`; placement `px-notification--top-right`, `--top-left`, `--bottom-right`, `--bottom-left`; JS state `px-notification--visible`, `px-notification--hiding`; `px-notification__content`, `px-notification__close`. Content uses `var(--font-size-sm)`, `var(--text)`; close hover uses `var(--surface)`, `var(--text)`, `var(--radius-sm)`, `var(--transition)`.

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

---

## Popover

Hover trigger + floating card. **Assets:** `popover.css`, `popover.js` (IIFE, no globals).

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Id on `px-popover-trigger`. |
| `content` | `str \| BaseComponent` | `""` | Trigger label (`px-popover-trigger__body`). |
| `card_content` | `str \| BaseComponent` | `""` | Panel body (`px-popover-card`). |
| `position` | literal | `"anchor"` | `anchor` (below trigger) or `follow` (pointer). → `data-popover-position`. |
| `backdrop` | `bool` | `False` | When `True`, emits `data-popover-backdrop` on the trigger (dim layer + lifted z-index). |

**Runtime behavior:** Mouse over the trigger opens the card; leaving the trigger (and its descendants) starts a short delayed hide. With **`data-popover-backdrop`** on the trigger (set `backdrop=True` on `Popover`, or add the attribute in custom markup), the script shows a full-screen dim layer, lifts the trigger z-index, and injects `#px-popover-backdrop` if needed.


### HTML

??? abstract "HTML (Jinja template)"

    ```html
    <span class="px-popover-trigger" id="{{ id }}" data-popover-position="{{ position }}"{% if backdrop %} data-popover-backdrop{% endif %}>
        <span class="px-popover-trigger__body">{{ content }}</span>
        <div class="px-popover-card" role="tooltip" aria-hidden="true">
            {{ card_content }}
        </div>
    </span>
    ```

### JavaScript

No exported functions. Behavior is driven by:

| Mechanism | Role |
| --- | --- |
| `.px-popover-trigger` / `.px-popover-card` | Discovery and visibility (`px-popover-card--visible`). |
| `data-popover-position` | `anchor` or `follow` (pointer tracking). |
| `data-popover-backdrop` | If present (any value), backdrop + trigger lift. |
| `#px-popover-backdrop` | Shared element; class `px-popover-backdrop`, state `px-popover-backdrop--visible`. |

### Style

**Classes:** `px-popover-trigger`, `px-popover-trigger__body`, `px-popover-card`, `px-popover-card--visible`, `px-popover-backdrop`, `px-popover-backdrop--visible`.

| Token | Default |
| --- | --- |
| `--px-popover-max-width` | `28ch` |
| `--px-popover-bg` | `var(--surface-alt)` |
| `--px-popover-border` | `var(--border)` |
| `--px-popover-radius` | `var(--radius-md)` |
| `--px-popover-shadow` | `var(--shadow-md)` |
| `--px-popover-padding` | `var(--space-3, 0.75rem) var(--space-4, 1rem)` |
| `--px-popover-z` | `300` |

Backdrop fill is fixed **`rgba(0, 0, 0, 0.35)`** in CSS (not a token). JS sets `z-index: calc(var(--px-popover-z) + 1)` on the trigger when the backdrop is active.

---

## LoadingOverlay

In-place loading veil over a positioned ancestor. **Assets:** `loading-overlay.css`, `loading-overlay.js`.

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Overlay root id for show/hide helpers. |

**Layout:** Overlay is `position: absolute; inset: 0`. Parent must be **`position: relative`** (or any non-`static` value) so coverage is correct.


### HTML

??? abstract "HTML (Jinja template)"

    ```html
    <div class="px-loading-overlay" id="{{ id }}" role="status" aria-label="Loading" aria-live="polite">
        <div class="px-loading-overlay__spinner"></div>
    </div>
    ```

### JavaScript

Globals from **`loading-overlay.js`**:

| Function | Description |
| --- | --- |
| `showLoadingOverlay(id)` | Removes `px-loading-overlay--hiding`, adds `px-loading-overlay--visible`. |
| `hideLoadingOverlay(id)` | Adds `px-loading-overlay--hiding`; on `animationend` clears visible/hiding classes. |

### Style

**Classes:** `px-loading-overlay`; state `px-loading-overlay--visible`, `px-loading-overlay--hiding`; `px-loading-overlay__spinner`. Spinner ring uses **`var(--radius-full)`** from your theme.

| Token | Default |
| --- | --- |
| `--px-loading-overlay-bg` | `rgb(0 0 0 / 0.55)` |
| `--px-loading-overlay-backdrop` | `blur(2px)` |
| `--px-loading-overlay-z` | `100` |
| `--px-loading-overlay-spinner-size` | `2.5rem` |
| `--px-loading-overlay-spinner-width` | `3px` |
| `--px-loading-overlay-spinner-color` | `var(--brand)` |
| `--px-loading-overlay-spinner-track` | `rgb(255 255 255 / 0.1)` |

---

## Tooltip

Compact focus/hover hint. **Assets:** `tooltip.css`, `tooltip.js` (IIFE).


### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root `px-tooltip` id; tip element id is `{{ id }}-tip`. |
| `trigger` | `str \| BaseComponent` | `""` | Focusable trigger (`px-tooltip__trigger`, `tabindex="0"`). |
| `tip` | `str \| BaseComponent` | `""` | `role="tooltip"` body. |
| `placement` | literal | `"top"` | `top`, `bottom`, `start`, `end` → `data-px-tooltip-placement`. |

**Tag gotcha:** If you use `Renderer.render()` with PascalCase tags, avoid both child text and a `content` attribute on components that map children to `content`—use body text as the child or attributes only, not both.

### Style tokens

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

---

## Alert

Inline status banner. **Assets:** `alert.css`, `alert.js`.


### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root id for `dismissPxAlert(id)`. |
| `variant` | literal | `"info"` | `info`, `success`, `warning`, `error` → `px-alert--{variant}`. |
| `title` | `str` | `""` | Optional heading. |
| `body` | `str \| BaseComponent` | `""` | Main copy. |
| `dismissible` | `bool` | `False` | When true, renders dismiss control calling `dismissPxAlert`. |

### JavaScript

| Function | Description |
| --- | --- |
| `dismissPxAlert(id)` | Adds `px-alert--dismissed` (hides via `display: none`). |

### Style tokens

| Token | Default |
| --- | --- |
| `--px-alert-radius` | `var(--radius-md)` |
| `--px-alert-padding` | `0.875rem 1rem` |
| `--px-alert-border` | `var(--border)` |
| `--px-alert-shadow` | `var(--shadow-md)` |
| `--px-alert-title-size` | `var(--font-size-sm)` |
| `--px-alert-body-size` | `var(--font-size-sm)` |
| `--px-alert-dismiss-color` | `var(--text-muted)` |

Variants use `color-mix` with `--brand`, `--success`, `--warning`, or `--error` / `--error-bg` / `--error-border` where applicable.

---

## Dropdown

Button + anchored panel. **Assets:** `dropdown.css`, `dropdown.js`.


### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Wrapper id; trigger id `{{ id }}-trigger`, menu `{{ id }}-menu`. |
| `trigger` | `str \| BaseComponent` | `""` | Button label. |
| `menu` | `str \| BaseComponent` | `""` | Panel HTML (e.g. links or custom markup). |

### JavaScript

| Function | Description |
| --- | --- |
| `togglePxDropdown(id)` | Toggles `hidden` on the menu and `aria-expanded` on the trigger. |
| `closePxDropdown(id)` | Closes the menu. |

**Listeners:** `document` `click` closes any open menu whose root does not contain the event target. `keydown` `Escape` closes all open menus.

### Style tokens

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

---

## Drawer

`<dialog>` sheet from an edge. **Assets:** `drawer.css`, `drawer.js`.


### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Dialog id for `openPxDrawer` / `closePxDrawer`. |
| `side` | literal | `"right"` | `left`, `right`, or `bottom` → `px-drawer--{side}`. |
| `title` | `str \| BaseComponent` | `""` | Header title. |
| `body` | `str \| BaseComponent` | `""` | Scrollable body. |
| `footer` | `str \| BaseComponent` | `""` | Optional footer strip. |

### JavaScript

| Function | Description |
| --- | --- |
| `openPxDrawer(id)` | `showModal()` on the dialog. |
| `closePxDrawer(id)` | Adds `px-drawer--closing`; on `animationend`, removes it and `dialog.close()`. |

**Listener:** `click` on `DIALOG.px-drawer` (backdrop hit) calls `closePxDrawer`—same pattern as modal; keep ids unique.

### Style tokens

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

---

## Progress

Determinate or indeterminate meter. **Assets:** `progress.css` only.


### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Wrapper id. |
| `value` | `float \| None` | `None` | Omit or `None` for indeterminate `<progress>`. |
| `max` | `float` | `100` | Passed to `<progress max="…">`. |
| `label` | `str` | `""` | Optional `px-progress__label`; wires `aria-labelledby` when set. |

### Style tokens

| Token | Default |
| --- | --- |
| `--px-progress-height` | `0.5rem` |
| `--px-progress-radius` | `var(--radius-full)` |
| `--px-progress-track` | `var(--surface-alt)` |
| `--px-progress-fill` | `var(--brand)` |
| `--px-progress-indeterminate-speed` | `1.2s` |

---

## Skeleton

Placeholder shimmer blocks. **Assets:** `skeleton.css` only.


### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root id. |
| `variant` | literal | `"text"` | `text` (stacked lines), `circle`, or `rect`. |
| `lines` | `int` | `3` | For `text`, count of `px-skeleton__line` rows. |
| `class_name` | `str` | `""` | Extra classes on the root. |

### Style tokens

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

---

## EmptyState

Centered empty view. **Assets:** `empty-state.css` only (template file **`empty-state.html`** next to `empty_state.py`).


### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root id. |
| `title` | `str \| BaseComponent` | `""` | Heading. |
| `description` | `str \| BaseComponent` | `""` | Supporting text. |
| `action` | `str \| BaseComponent` | `""` | Optional slot (e.g. button markup). |

### Style tokens

| Token | Default |
| --- | --- |
| `--px-empty-state-padding` | `2rem 1.5rem` |
| `--px-empty-state-max-width` | `28rem` |
| `--px-empty-state-title-size` | `var(--font-size-md)` |
| `--px-empty-state-desc-size` | `var(--font-size-sm)` |
| `--px-empty-state-title-color` | `var(--text)` |
| `--px-empty-state-desc-color` | `var(--text-muted)` |
| `--px-empty-state-gap` | `0.5rem` |

---

## Divider

Separator line. **Assets:** `divider.css` only.

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root id. |
| `orientation` | literal | `"horizontal"` | `horizontal` (default `hr`) or `vertical` (bar). |
| `label` | `str` | `""` | If set with horizontal orientation, flex row with label between lines. |
| `class_name` | `str` | `""` | Extra classes on the root. |

### HTML

??? abstract "HTML (Jinja template)"

    ```jinja
    {% if orientation == 'vertical' %}
    <div id="{{ id }}"
         class="px-divider px-divider--vertical{% if class_name %} {{ class_name }}{% endif %}"
         role="separator"
         aria-orientation="vertical"
         {% if label %}aria-label="{{ label }}"{% endif %}></div>
    {% elif label %}
    <div id="{{ id }}" class="px-divider px-divider--labeled{% if class_name %} {{ class_name }}{% endif %}" role="presentation">
      <span class="px-divider__line" aria-hidden="true"></span>
      <span class="px-divider__label">{{ label }}</span>
      <span class="px-divider__line" aria-hidden="true"></span>
    </div>
    {% else %}
    <hr id="{{ id }}"
        class="px-divider px-divider--horizontal{% if class_name %} {{ class_name }}{% endif %}"
        role="separator"
        aria-orientation="horizontal" />
    {% endif %}
    ```

### JavaScript

No bundled script.

### Style

**Classes:** `px-divider--horizontal`, `px-divider--vertical`, `px-divider--labeled`, `px-divider__line`, `px-divider__label`.

| Token | Default |
| --- | --- |
| `--px-divider-color` | `var(--border)` |
| `--px-divider-thickness` | `1px` |
| `--px-divider-gap` | `0.75rem` |
| `--px-divider-label-color` | `var(--text-muted)` |
| `--px-divider-label-size` | `var(--font-size-sm)` |

---

## Spinner

Inline loading indicator. **Assets:** `spinner.css` only.

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root id. |
| `size` | literal | `"md"` | `sm`, `md`, or `lg`. |
| `label` | `str` | `"Loading"` | Visually hidden; exposed to assistive tech. |

### HTML

??? abstract "HTML (Jinja template)"

    ```jinja
    <span id="{{ id }}"
          class="px-spinner px-spinner--{{ size }}"
          role="status"
          aria-live="polite"
          aria-busy="true">
      <span class="px-spinner__ring" aria-hidden="true"></span>
      <span class="px-spinner__label">{{ label }}</span>
    </span>
    ```

### JavaScript

No bundled script.

### Style

**Classes:** `px-spinner`, `px-spinner--sm|md|lg`, `px-spinner__ring`, `px-spinner__label` (screen-reader-only).

| Token | Default |
| --- | --- |
| `--px-spinner-sm` | `1.25rem` |
| `--px-spinner-md` | `2rem` |
| `--px-spinner-lg` | `2.75rem` |
| `--px-spinner-track` | `color-mix(in srgb, var(--text-muted) 35%, transparent)` |
| `--px-spinner-accent` | `var(--brand)` |

---

## Avatar

Image or initials in a circle. **Assets:** `avatar.css` only (template **`avatar.html`**).

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root id. |
| `src` | `str` | `""` | Image URL; when empty, initials fallback is shown. |
| `alt` | `str` | `""` | `img` alt text; also used as `title` on initials. |
| `initials` | `str` | `""` | Up to two characters (trimmed/capped in validation). |
| `size` | literal | `"md"` | `sm`, `md`, or `lg`. |
| `class_name` | `str` | `""` | Extra classes on the root. |

### HTML

??? abstract "HTML (Jinja template)"

    ```jinja
    <div id="{{ id }}"
         class="px-avatar px-avatar--{{ size }}{% if class_name %} {{ class_name }}{% endif %}">
      {% if src %}
      <img class="px-avatar__img" src="{{ src }}" alt="{{ alt }}" loading="lazy" decoding="async" />
      {% else %}
      <span class="px-avatar__initials" {% if alt %}title="{{ alt }}"{% endif %}>{{ initials or "?" }}</span>
      {% endif %}
    </div>
    ```

### JavaScript

No bundled script.

### Style

**Classes:** `px-avatar`, `px-avatar--sm|md|lg`, `px-avatar__img`, `px-avatar__initials`.

| Token | Default |
| --- | --- |
| `--px-avatar-sm` | `2rem` |
| `--px-avatar-md` | `2.5rem` |
| `--px-avatar-lg` | `3.25rem` |
| `--px-avatar-bg` | `var(--surface-alt)` |
| `--px-avatar-fg` | `var(--text-muted)` |
| `--px-avatar-border` | `var(--border)` |

---

## Card

Grouped content with optional header and footer. **Assets:** `card.css` only.

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root id. |
| `title` | `str \| BaseComponent` | `""` | Default header title (ignored if `header` is set). |
| `header` | `str \| BaseComponent` | `""` | Custom header slot; replaces `title` block when set. |
| `body` | `str \| BaseComponent` | `""` | Main content. |
| `footer` | `str \| BaseComponent` | `""` | Optional footer. |

### HTML

??? abstract "HTML (Jinja template)"

    ```jinja
    <article id="{{ id }}" class="px-card">
      {% if header or title %}
      <header class="px-card__header">
        {% if header %}
        {{ header }}
        {% else %}
        <h3 class="px-card__title">{{ title }}</h3>
        {% endif %}
      </header>
      {% endif %}
      <div class="px-card__body">{{ body }}</div>
      {% if footer %}
      <footer class="px-card__footer">{{ footer }}</footer>
      {% endif %}
    </article>
    ```

### JavaScript

No bundled script.

### Style

**Classes:** `px-card`, `px-card__header`, `px-card__title`, `px-card__body`, `px-card__footer`.

| Token | Default |
| --- | --- |
| `--px-card-bg` | `var(--surface-alt)` |
| `--px-card-border` | `var(--border)` |
| `--px-card-radius` | `var(--radius-md)` |
| `--px-card-title-color` | `var(--text)` |
| `--px-card-padding` | `var(--space-4, 1rem)` |

---

## Breadcrumb

Ordered trail of links. **Assets:** `breadcrumb.css` only.

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root `nav` id. |
| `items` | `list[tuple[str, str \| None]]` | `[]` | `(label, href)` left to right; `href` `None` marks the current page. |

`items` may also be passed as a **JSON array** string (e.g. from PascalCase tags): `[["Home","/"],["Here",null]]`.

### HTML

??? abstract "HTML (Jinja template)"

    ```jinja
    <nav id="{{ id }}" class="px-breadcrumb" aria-label="Breadcrumb">
      <ol class="px-breadcrumb__list">
        {% for label, href in items %}
        <li class="px-breadcrumb__item">
          {% if href %}
          <a class="px-breadcrumb__link" href="{{ href }}">{{ label }}</a>
          {% else %}
          <span class="px-breadcrumb__current" aria-current="page">{{ label }}</span>
          {% endif %}
        </li>
        {% endfor %}
      </ol>
    </nav>
    ```

### JavaScript

No bundled script.

### Style

**Classes:** `px-breadcrumb`, `px-breadcrumb__list`, `px-breadcrumb__item`, `px-breadcrumb__link`, `px-breadcrumb__current`. Separators via `::after` on items except the last.

| Token | Default |
| --- | --- |
| `--px-breadcrumb-sep` | `"/"` |
| `--px-breadcrumb-link-color` | `var(--brand)` |
| `--px-breadcrumb-current-color` | `var(--text)` |

---

## TabGroup

Tab buttons and panels. **Assets:** `tab-group.css`, **`tab-group.js`** (kebab-case filenames so the renderer’s JS/CSS collector finds them; see `LoadingOverlay` → `loading-overlay.*`).

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root id; tab and panel ids are derived from it. |
| `tabs` | `dict[str, str \| BaseComponent]` | `{}` | **Insertion order** is tab order; keys are labels, values are panel bodies. |

`tabs` may also be a **JSON object** string from markup tags (values are HTML strings).

### HTML

??? abstract "HTML (Jinja template)"

    ```jinja
    <div id="{{ id }}" class="px-tab-group">
      <div class="px-tab-group__list" role="tablist" aria-label="Tabs">
        {% for label, panel in tabs.items() %}
        <button type="button"
                class="px-tab-group__tab"
                role="tab"
                id="{{ id }}-tab-{{ loop.index0 }}"
                aria-controls="{{ id }}-panel-{{ loop.index0 }}"
                aria-selected="{% if loop.first %}true{% else %}false{% endif %}"
                tabindex="{% if loop.first %}0{% else %}-1{% endif %}">{{ label }}</button>
        {% endfor %}
      </div>
      {% for label, panel in tabs.items() %}
      <div class="px-tab-group__panel"
           role="tabpanel"
           id="{{ id }}-panel-{{ loop.index0 }}"
           aria-labelledby="{{ id }}-tab-{{ loop.index0 }}"
           {% if not loop.first %}hidden{% endif %}>{{ panel }}</div>
      {% endfor %}
    </div>
    ```

### JavaScript

**`tab-group.js`:** `click` delegation on `.px-tab-group__tab` updates `aria-selected`, `tabindex`, and `hidden` on sibling panels within the same `.px-tab-group`.

### Style

**Classes:** `px-tab-group`, `px-tab-group__list`, `px-tab-group__tab`, `px-tab-group__panel`.

| Token | Default |
| --- | --- |
| `--px-tab-group-border` | `var(--border)` |
| `--px-tab-group-bg` | `var(--surface-alt)` |
| `--px-tab-group-tab-active-fg` | `var(--text)` |
| `--px-tab-group-tab-active-bg` | `color-mix(in srgb, var(--surface) 55%, var(--surface-alt))` |
| `--px-tab-group-tab-active-border` | `var(--brand)` |
| `--px-tab-group-panel-bg` | `var(--surface)` |

---

## Region

Panel host for **distributed** tab-like switching: all bodies render here; controls are separate [`RegionTrigger`](#regiontrigger) components. **Unstyled** aside from `hidden` panels. **Assets:** `region.css`, **`region.js`**.

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Root id; must match `RegionTrigger.region_id`. Panel element ids are `{{ id }}-panel-{{ key }}`. |
| `panels` | `dict[str, str \| BaseComponent]` | `{}` | **Insertion order** sets the initially visible panel (first is shown). Keys must match `[a-zA-Z0-9_-]+`. |

`panels` may be a **JSON object** string from PascalCase tags. Keys are used in HTML `id` attributes and `data-px-region-panel`.

### HTML

??? abstract "HTML (Jinja template)"

    ```jinja
    <div id="{{ id }}" class="px-region">
      {% for panel_key, panel_body in panels.items() %}
      <div class="px-region__panel"
           role="tabpanel"
           id="{{ id }}-panel-{{ panel_key }}"
           data-px-region-panel="{{ panel_key }}"
           {% if not loop.first %}hidden{% endif %}>{{ panel_body }}</div>
      {% endfor %}
    </div>
    ```

### JavaScript

**`region.js`:** `click` on `.px-region-trigger` shows the matching `.px-region__panel` inside the host `getElementById(region_id)`, hides others, syncs `aria-selected` / `tabIndex` on **all** triggers for that `region_id`. **`pxRegionInit`** runs on `DOMContentLoaded`, `htmx:afterSwap`, and `htmx:afterSettle` so swapped fragments pick up correct ARIA after partial updates.

### Style

**Classes:** `px-region`, `px-region__panel`. No theme tokens; minimal rules for `[hidden]` panels.

---

## RegionTrigger

Button that activates a panel inside a [`Region`](#region) (may be placed anywhere in the layout). **Assets:** none (uses `region.js` from `Region`). **Unstyled** (browser default button).

### Python

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | `str` | (required) | Button id. |
| `region_id` | `str` | (required) | Must equal the target `Region.id`. |
| `panel` | `str` | (required) | Key matching a key in `Region.panels`; `[a-zA-Z0-9_-]+`. |
| `label` | `str \| BaseComponent` | `""` | Button label. |

### HTML

??? abstract "HTML (Jinja template)"

    ```jinja
    <button type="button"
            id="{{ id }}"
            class="px-region-trigger"
            role="tab"
            data-px-region="{{ region_id }}"
            data-px-region-panel="{{ panel }}"
            aria-controls="{{ region_id }}-panel-{{ panel }}"
            aria-selected="false"
            tabindex="-1">{{ label }}</button>
    ```

### JavaScript

Bundled with **`region.js`** (collected when either `Region` or `RegionTrigger` is rendered from the same package directory).

### Style

No component CSS file; override `.px-region-trigger` in your app if needed.

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
    Region,
    RegionTrigger,
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
main_region = Region(
    id="app-region",
    panels={"chat": "<p>Chat UI</p>", "other": "<p>Other</p>"},
)
open_chat = RegionTrigger(id="open-chat", region_id="app-region", panel="chat", label="Chat")
```
