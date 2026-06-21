# Built-in UI components

Optional package **`pyjinhx.builtins`** registers thirty-seven [`BaseComponent`](../api/base-component.md) subclasses. Import:

```python
from pyjinhx.builtins import (
    PJXAccordion,
    PJXAccordionGroup,
    PJXAlert,
    PJXAvatar,
    PJXAvatarStack,
    PJXBadge,
    PJXBreadcrumb,
    PJXButton,
    PJXCard,
    PJXChipInput,
    PJXConfirmDialog,
    PJXDivider,
    PJXDropdown,
    PJXDrawer,
    PJXEmptyState,
    PJXFormField,
    PJXIcon,
    PJXLazyPanel,
    PJXRegionLoader,
    PJXModal,
    PJXNotification,
    PJXPageLoader,
    PJXPasswordInput,
    PJXPopover,
    PJXPopoverPanel,
    PJXPopoverTrigger,
    PJXProgress,
    PJXPromptDialog,
    PJXPanel,
    PJXPanelTrigger,
    PJXSegmentedControl,
    PJXSkeleton,
    PJXSpinner,
    PJXTabGroup,
    PJXToastHost,
    PJXToggleSwitch,
    PJXTooltip,
    PJXTooltipContent,
    PJXTooltipTrigger,
)
```

`__all__` matches that set of thirty-nine names.

**Conventions:** Markup classes use the **`pjx-`** prefix; overrides use **`--pjx-`** custom properties. Builtin CSS also references **theme variables** (`--surface`, `--border`, `--text`, `--radius-md`, `--shadow-md`, `--transition`, `--brand`, …)—define those in your global CSS or map them to your design system. See [builtin-conventions.md](./builtin-conventions.md) for the full per-component contract (auto-id, `class_name`, `extra_attrs`, `js`/`css`, headless IIFE JS under `window.pjx`, cancelable `pjx:*:before-*` events).

**Template discovery:** Builtins ship inside `site-packages`, not under your app's Jinja loader root, so PascalCase tags do **not** auto-discover them — `<PJXTooltip/>` raises a `FileNotFoundError` unless the class was imported once at startup (`import pyjinhx.builtins` or any of the imports above), which registers it. For registered builtin classes, the renderer **falls back** to adjacent package templates: each component's Jinja template lives next to its Python source in `pyjinhx/builtins/ui/pjx_<component>/` (e.g. `pyjinhx/builtins/ui/pjx_modal/pjx_modal.html`). Subclasses of builtins inherit the builtin's template and assets through the MRO, so `class TaskBadge(PJXBadge)` renders like a PJXBadge — see the [reactivity guide](../reactivity.md#making-builtins-reactive) for the reactive pattern.

**Inherited fields:** Every component inherits `id`, `js`/`css` (extra-asset fields — see [BaseComponent](../api/base-component.md)), `class_name`, `extra_attrs`, `render()`, and `__html__()` — see [builtin-conventions.md](./builtin-conventions.md) for the full contract. `id` is omitted from per-component props tables below.

**Theming:** Per-component `--pjx-*` tokens are collected in the [Theming tokens](#theming-tokens) appendix. Each component section points there.

**Asset summary:**

| Component | CSS | JS |
|---|---|---|
| PJXAccordion | `pjx-accordion.css` | — |
| PJXAccordionContent | — | — |
| PJXAccordionTrigger | `pjx-accordion-trigger.css` | `pjx-accordion-trigger.js` |
| PJXAccordionGroup | `pjx-accordion-group.css` | `pjx-accordion-group.js` |
| PJXAlert | `pjx_alert.css` | `pjx_alert.js` |
| PJXAvatar | `pjx_avatar.css` | — |
| PJXAvatarStack | `pjx-avatar-stack.css` | — |
| PJXBadge | `pjx_badge.css` | — |
| PJXBreadcrumb | `pjx_breadcrumb.css` | — |
| PJXButton | `pjx-button.css` | — |
| PJXCard | `pjx-card.css` | — |
| PJXCardHeader | `pjx-card-header.css` | — |
| PJXCardBody | `pjx-card-body.css` | — |
| PJXCardFooter | `pjx-card-footer.css` | — |
| PJXChipInput | `pjx-chip-input.css` | `pjx-chip-input.js` |
| PJXConfirmDialog | `pjx-confirm-dialog.css` | `pjx-confirm-dialog.js` |
| PJXDivider | `pjx_divider.css` | — |
| PJXDrawer | `pjx-drawer.css` | `pjx-drawer.js` |
| PJXDrawerHeader | `pjx-drawer-header.css` | — |
| PJXDrawerBody | `pjx-drawer-body.css` | — |
| PJXDrawerFooter | `pjx-drawer-footer.css` | — |
| PJXDropdown | `pjx_dropdown.css` | *(via pjx_popover.js, extra-asset)* |
| PJXEmptyState | `pjx-empty-state.css` | — |
| PJXFormField | `pjx-form-field.css` | — |
| PJXIcon | `pjx-icon.css` | — |
| PJXLazyPanel | — | — |
| PJXRegionLoader | `pjx-region-loader.css` | `pjx-region-loader.js` |
| PJXModal | `pjx-modal.css` | `pjx-modal.js` |
| PJXModalHeader | `pjx-modal-header.css` | — |
| PJXModalBody | `pjx-modal-body.css` | — |
| PJXModalFooter | `pjx-modal-footer.css` | — |
| PJXNotification | `pjx_notification.css` | `pjx_notification.js` |
| PJXPageLoader | `pjx-page-loader.css` | `pjx-page-loader.js` |
| PJXPanel | `pjx_panel.css` | `pjx_panel.js` |
| PJXPanelTrigger | `pjx-panel-trigger.css` | *(pjx_panel.js from PJXPanel)* |
| PJXPasswordInput | `pjx-password-input.css` | `pjx-password-input.js` |
| PJXPopover | `pjx_popover.css` | `pjx_popover.js` |
| PJXPopoverPanel | *(from PJXPopover)* | *(from PJXPopover)* |
| PJXPopoverTrigger | *(from PJXPopover)* | *(from PJXPopover)* |
| PJXProgress | `pjx_progress.css` | — |
| PJXPromptDialog | `pjx-prompt-dialog.css` | `pjx-prompt-dialog.js` |
| PJXSegmentedControl | `pjx-segmented-control.css` | — |
| PJXSkeleton | `pjx_skeleton.css` | — |
| PJXSpinner | `pjx_spinner.css` | — |
| PJXTabGroup | `pjx-tab-group.css` | `pjx-tab-group.js` |
| PJXToastHost | `pjx-toast-host.css` | `pjx-toast-host.js` |
| PJXToggleSwitch | `pjx-toggle-switch.css` | — |
| PJXTooltip | `pjx-tooltip.css` | `pjx-tooltip.js` (IIFE, no API) |
| PJXTooltipTrigger | `pjx-tooltip-trigger.css` | — |
| PJXTooltipContent | `pjx-tooltip-content.css` | — |

**Children-vs-`content` tag gotcha (children-mapping components):** Several components map children to a single attribute (e.g. PJXNotification `content`, PJXPanelTrigger `content`, PJXTooltip `content`). If you use `Renderer.render()` with PascalCase tags, do **not** supply both child text and the corresponding attribute on the same tag—use body text as the child *or* the attribute, not both.

**Backdrop click (PJXModal and PJXDrawer):** Both render a native `<dialog>`; a document `click` listener treats a click whose target is the `<dialog>` root itself (the backdrop) as a close. Any native `<dialog>` clicked directly is affected—use unique ids and avoid stacking multiple dialogs unless you adjust this.

**`pjx_panel.js` loading:** `pjx_panel.js` is included only when a [`PJXPanel`](#pjxpanel) is rendered on the page. [`PJXPanelTrigger`](#pjxpaneltrigger) does **not** load `pjx_panel.js` by asset name, so render a `PJXPanel` on the same page (or add the script yourself) for triggers to work.

---

## PJXBadge

Small status label. **Assets:** `pjx_badge.css` only.

<!-- demo: PJXBadge -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `label` | `str` | `""` | Inner text. |
| `color` | literal | `"neutral"` | `brand`, `error`, `neutral`, `muted` → `pjx-badge--{color}`. |
| `shape` | literal | `"md"` | `square`, `sm`, `md`, `full` → `pjx-badge--{shape}`. |

**DOM contract.** Root `.pjx-badge`; no JS API.

**Classes:** `pjx-badge`; color modifiers `pjx-badge--brand`, `--error`, `--neutral`, `--muted`; shape `pjx-badge--square`, `--sm`, `--md`, `--full`. Theming: see [PJXBadge tokens](#pjxbadge-tokens).

---

## PJXIcon

Inline SVG icon from a vendored [Lucide](https://lucide.dev) set (ISC). **Assets:** `pjx-icon.css` only.

<!-- demo: PJXIcon -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `str` | *(required)* | Icon key into the vendored set (e.g. `chevron-right`, `plus`, `search`). An unknown name renders a hidden placeholder (nothing visible) and logs a warning. |
| `size` | `int \| str` | `16` | `int` → `width`/`height` in px; `str` → used verbatim as a CSS length. |
| `stroke_width` | `float` | `1.5` | SVG `stroke-width`. |
| `label` | `str \| None` | `None` | `None` → `aria-hidden="true"`; a string → `role="img"` + a `<title>`. |

**DOM contract.** Root `<svg>` with `stroke="currentColor"` and `fill="none"`; no JS API. It inherits text color, so it themes for free — set `color` on the icon or any ancestor. Compose into slots, e.g. `<PJXButton start="<PJXIcon name='plus'/>" center="Add"/>`.

**Classes:** `pjx-icon`. Theming: no `--pjx-icon-*` tokens — size comes from the `size`/`stroke_width` props and color from `currentColor`.

---

## PJXButton

Structural, themeable button. Composes [`PJXRegionLoader`](#pjxregionloader) for the inline loading state. **Assets:** `pjx-button.css` only.

<!-- demo: PJXButton -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `start` | `str \| BaseComponent \| None` | `None` | Leading slot (e.g. an icon); the `.pjx-button__start` span is omitted when empty. |
| `center` | `str \| None` | `None` | Label text (`.pjx-button__center`), HTML-escaped; omitted when empty. Use `start`/`end` for icon slots. |
| `end` | `str \| BaseComponent \| None` | `None` | Trailing slot (icon/badge, `.pjx-button__end`), omitted when empty. |
| `variant` | `str` | `"default"` | Class hook only → `pjx-button--{variant}`. No baked palette; style it yourself. |
| `block` | `bool` | `False` | Full-width (`pjx-button--block`) instead of content-width. |
| `loading` | `bool` | `False` | Renders a `<PJXRegionLoader/>` overlay and sets `aria-busy="true"`. |
| `disabled` | `bool` | `False` | Sets the `disabled` attribute. |
| `type` | literal | `"button"` | `button`, `submit`, or `reset`. |

**DOM contract.** Root `<button>`; slot spans render only when their value is set. No JS API — pass `hx-*`/`@click` inline (they pass through to the root). The default `.pjx-button` is visually neutral so it never fights your design system; paint variants via `.pjx-button--<variant>`.

**Classes:** `pjx-button`; `pjx-button--block`; variant seams `pjx-button--<variant>`; `pjx-button__start`, `__center`, `__end`. Theming: see [PJXButton tokens](#pjxbutton-tokens).

---

## PJXAccordion

Collapsible section built on native `<details>`. Composed with `PJXAccordionTrigger` (the `<summary>`, with the auto chevron) and `PJXAccordionContent` (the body). **Assets:** `pjx-accordion.css` (shell radius only — trigger and chevron CSS ship with `PJXAccordionTrigger`). No JS.

<!-- demo: PJXAccordion -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `open` | `bool` | `True` | Initial expanded state (renders the `open` attribute on `<details>`). |
| `group` | `str \| None` | `None` | Native `<details name="...">` for exclusive-open groups; default is independent multi-open. |
| `content` | `str \| BaseComponent` | `""` | Inner HTML; nest a `PJXAccordionTrigger` + `PJXAccordionContent` here. |

**DOM contract.** Root `<details class="pjx-accordion">` rendering `{{ content }}` verbatim. Place a `PJXAccordionTrigger` and a `PJXAccordionContent` inside `content` to form a complete accordion.

**Classes:** `pjx-accordion`. Theming: see [PJXAccordion tokens](#pjxaccordion-tokens).

---

## PJXAccordionTrigger

The `<summary>` part of a composed accordion. Composes [`PJXIcon`](#pjxicon) for the disclosure chevron. **Assets:** `pjx-accordion-trigger.css` (trigger + chevron styles), `pjx-accordion-trigger.js` (toggle-suppression for opt-in `pjx-accordion__actions`).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `disabled` | `bool` | `False` | Marks the summary `aria-disabled="true"` + `tabindex="-1"` (and `pointer-events: none` via CSS). |
| `class_name` | `AttrValue` | `""` | Extra CSS class(es) for the root element. |
| `content` | `str \| BaseComponent` | `""` | Trigger label (text or rich markup). |

**DOM contract.** Root `<summary class="pjx-accordion__trigger">` containing the auto-chevron and `content`. The chevron rotates on `[open]` via CSS. The default marker is stripped.

**Actions (opt-in).** To add non-toggling action buttons, wrap them in `<div class="pjx-accordion__actions">` inside `content`. `pjx-accordion-trigger.js` registers a single capture-phase `click` listener that calls `preventDefault()` (only — deliberately **not** `stopPropagation()`) for any click inside `.pjx-accordion__actions`. This cancels the native `<summary>` toggle while leaving htmx and other handlers intact.

**Classes:** `pjx-accordion__trigger`, `pjx-accordion__chevron`, `pjx-accordion__actions`. Theming: see [PJXAccordion tokens](#pjxaccordion-tokens).

---

## PJXAccordionContent

The body part of a composed accordion. **Assets:** none (unstyled wrapper; use your own or theme the parent shell).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `class_name` | `AttrValue` | `""` | Extra CSS class(es) for the root element. |
| `content` | `str \| BaseComponent` | `""` | Body content. |

**DOM contract.** Root `<div class="pjx-accordion__content">` rendering `{{ content }}` verbatim.

**Classes:** `pjx-accordion__content`. No theming tokens — style via the parent `pjx-accordion` or your own rules.

---

## PJXAccordionGroup

Groups a set of `PJXAccordion`s into a shared layout/behavior container. Handles exclusive-open coordination in JS so you don't need to stamp a `group=` on every child. **Assets:** `pjx-accordion-group.css`, `pjx-accordion-group.js`.

<!-- demo: PJXAccordionGroup -->

```python
def item(title, body, **kw):
    return PJXAccordion(
        content=PJXAccordionTrigger(content=title).render()
        + PJXAccordionContent(content=body).render(),
        **kw,
    ).render()

PJXAccordionGroup(
    id="faq",
    mode="exclusive",
    gap="0.25rem",
    content=item("What is it?", "<p>A framework.</p>")
    + item("How to install?", "<p>pip install pyjinhx</p>", open=False),
)
```

Or with PascalCase tags:

```html
<PJXAccordionGroup mode="exclusive" gap="0.25rem">
  <PJXAccordion id="faq-a">
    <PJXAccordionTrigger>What is pyjinhx?</PJXAccordionTrigger>
    <PJXAccordionContent><p>A Python/Jinja HTML component framework.</p></PJXAccordionContent>
  </PJXAccordion>
  <PJXAccordion id="faq-b" open="False">
    <PJXAccordionTrigger>How do I install it?</PJXAccordionTrigger>
    <PJXAccordionContent>pip install pyjinhx</PJXAccordionContent>
  </PJXAccordion>
</PJXAccordionGroup>
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `mode` | `"exclusive" \| "multi"` | `"multi"` | `exclusive` — at most one child `<details>` open at a time (JS-coordinated via `toggle` capture); `multi` — independent. |
| `gap` | `str` | `"0"` | Space between accordion items; written to `--pjx-accordion-group-gap` inline on the root. |
| `default_open` | `"none" \| "first" \| "all"` | `"none"` | Which items start open on mount. `none` — no change (each child respects its own `open` prop); `first` — JS opens the first direct `<details>` child; `all` — JS opens all direct `<details>` children. Applied by `pjx-accordion-group.js` after DOM settle. |
| `content` | `str \| BaseComponent` | `""` | Children (nested `PJXAccordion`s or raw HTML). |

**DOM contract.** Root `<div class="pjx-accordion-group" data-pjx-accordion-group data-mode="..." [data-default-open="..."]>`. `pjx-accordion-group.js` runs once per element (guarded by `data-pjx-group-init`), applies `default_open`, then wires the exclusive-open `toggle` listener when `mode="exclusive"`. Re-initialized on `htmx:afterSettle`.

**`default_open` is JS-driven.** The group receives its `content` as a pre-rendered string, so it cannot set the `open` attribute on individual child elements at the server level. Instead, `data-default-open` is emitted on the root div and `pjx-accordion-group.js` opens the appropriate children on mount (and after every htmx swap). Per-child `open=True/False` props are still respected when `default_open="none"`.

**JS is always loaded with the group asset.** The script is a compact guarded IIFE; it exits early per-element when neither `mode="exclusive"` nor `data-default-open` requires action. In pure `multi` mode with `default_open="none"` (the defaults) the only runtime cost is the per-element `data-pjx-group-init` guard check.

**Design decision — JS vs native `<details name>`.** Native `<details name="...">` provides exclusive-open without JS, but requires stamping the same `name` on every child element. `PJXAccordion.group=` exposes this as an explicit per-child opt-in (still supported, not deprecated). `PJXAccordionGroup(mode="exclusive")` is the composition-friendly alternative: the group's capture-phase `toggle` listener handles exclusive-open so callers don't set `group=` on every child. The two approaches are independent and can coexist.

**Classes:** `pjx-accordion-group`. Theming: see [PJXAccordionGroup tokens](#pjxaccordiongroup-tokens).

---

## PJXModal

Native `<dialog>` shell. Compose with `PJXModalHeader`, `PJXModalBody`, and `PJXModalFooter` for structured layouts. **Assets:** `pjx-modal.css`, `pjx-modal.js`.

<!-- demo: PJXModal -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Inner content (part components or arbitrary markup). |
| `open_on_mount` | `bool` | `False` | When `True`, adds `data-pjx-open-on-mount`; JS opens the dialog as soon as it mounts (e.g. via `hx-swap="beforeend"`). |
| `remove_on_close` | `bool` | `False` | When `True`, adds `data-pjx-remove-on-close`; JS removes the element from the DOM on close. |
| `class_name` | `str` | `""` | Extra CSS classes on the root `<dialog>`. |

```html
<button data-pjx-open="confirm">Open</button>
<PJXModal id="confirm">
  <PJXModalHeader title="Delete file?"/>
  <PJXModalBody>This cannot be undone.</PJXModalBody>
  <PJXModalFooter><PJXButton center="Delete"/></PJXModalFooter>
</PJXModal>
```

**DOM contract.** Root `dialog.pjx-modal` (state: `[open]`, `.pjx-modal--closing`).
Attributes: `data-pjx-open="<id>"` on any element opens it on click; `data-pjx-close` inside closes it;
`data-pjx-open-on-mount`, `data-pjx-remove-on-close` reflect the lifecycle props.
Events (bubble from the root): `pjx:modal:before-open`*, `pjx:modal:open`,
`pjx:modal:before-close`*, `pjx:modal:close` — `*` = cancelable, `detail = {reason, trigger}`,
`reason ∈ escape|backdrop|api|trigger`. API: `pjx.modal.open(id)`, `pjx.modal.close(id)`.

**Classes:** `pjx-modal`; closing state `pjx-modal--closing`; `pjx-modal__box`. Part-component classes (`__header`, `__title`, `__close`, `__body`, `__footer`) belong to the respective part components below. Theming: see [PJXModal tokens](#pjxmodal-tokens).

---

## PJXModalHeader

Header part for `PJXModal`. Renders a `<header>` inside the modal box; always includes a close button. **Assets:** `pjx-modal-header.css`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `title` | `str` | `""` | When set, renders `<span class="pjx-modal__title">` with this text (escaped); when empty, `{{ content }}` is used instead. |
| `close_label` | `str` | `"Close"` | `aria-label` for the auto-included close button. |
| `close_content` | `str` | `"✕"` | Inner markup/text of the close button. |
| `class_name` | `str` | `""` | Extra CSS classes on the `<header>`. |
| `content` | `str \| BaseComponent` | `""` | Custom header body; used when `title` is empty. |

```html
<PJXModalHeader title="Delete file?"/>
```

**Classes:** `pjx-modal__header`, `pjx-modal__title`, `pjx-modal__close`.

---

## PJXModalBody

Body part for `PJXModal`. Renders a `<div class="pjx-modal__body">`. **Assets:** `pjx-modal-body.css`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `class_name` | `str` | `""` | Extra CSS classes on the body `<div>`. |
| `content` | `str \| BaseComponent` | `""` | Main content. |

```html
<PJXModalBody>This cannot be undone.</PJXModalBody>
```

**Classes:** `pjx-modal__body`.

---

## PJXModalFooter

Footer part for `PJXModal`. Renders a `<footer class="pjx-modal__footer">`. **Assets:** `pjx-modal-footer.css`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `class_name` | `str` | `""` | Extra CSS classes on the `<footer>`. |
| `content` | `str \| BaseComponent` | `""` | Footer content (e.g. action buttons). |

```html
<PJXModalFooter><PJXButton center="Delete"/></PJXModalFooter>
```

**Classes:** `pjx-modal__footer`.

---

## PJXNotification

Fixed-position toast. **Assets:** `pjx_notification.css`, `pjx_notification.js`.

<!-- demo: PJXNotification -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Message body. |
| `corner` | literal | `"top-right"` | `top-right`, `top-left`, `bottom-right`, `bottom-left`. |
| `timeout` | `int` | `5000` | Auto-dismiss ms; `0` disables. Rendered as `data-timeout`. |
| `autoshow` | `bool` | `True` | When `True`, adds `data-pjx-autoshow`; JS shows the notification as soon as it mounts. |
| `dismiss_label` | `str` | `"Dismiss"` | `aria-label` for the dismiss button. |

**DOM contract.** Root `.pjx-notification` (state: `.pjx-notification--visible`, `.pjx-notification--hiding`).
`data-pjx-autoshow` triggers auto-show on mount. `data-pjx-close` inside hides it.
Events: `pjx:notification:before-show`*, `pjx:notification:show`, `pjx:notification:before-hide`*, `pjx:notification:hide` — `*` = cancelable, `detail = {reason, trigger}`.
API: `pjx.notification.show(id)`, `pjx.notification.hide(id)`.

Maps children to `content`; see the [children-vs-`content` note](#built-in-ui-components).

**Classes:** `pjx-notification`; placement `pjx-notification--top-right`, `--top-left`, `--bottom-right`, `--bottom-left`; JS state `pjx-notification--visible`, `pjx-notification--hiding`; `pjx-notification__content`, `pjx-notification__close`. Theming: see [PJXNotification tokens](#pjxnotification-tokens).

---

## PJXPopover

Click-toggle compound. Three separate components; compose them by placing `PJXPopoverTrigger` and `PJXPopoverPanel` **as children inside `PJXPopover`**. **Assets:** `pjx_popover.css`, `pjx_popover.js` (IIFE under `pjx.popover`).

<!-- demo: PJXPopover -->

```python
PJXPopover(
    id="menu",
    content=(
        PJXPopoverTrigger(id="menu-t", content="Open").render()
        + PJXPopoverPanel(id="menu-p", role="menu", content="…").render()
    ),
)
```

Or with PascalCase tags:

```html
<PJXPopover id="menu">
  <PJXPopoverTrigger id="menu-t">Open</PJXPopoverTrigger>
  <PJXPopoverPanel id="menu-p" role="menu">…</PJXPopoverPanel>
</PJXPopover>
```

### PJXPopover

Root wrapper — sets up the `data-pjx-popover` attribute scope.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Children (trigger + panel). |
| `align` | literal | `"start"` | `start` or `end` (panel alignment) → `pjx-popover--align-end`. |
| `behavior` | `bool` | `True` | When `True`, adds `data-pjx-popover` (JS picks it up). |

### PJXPopoverTrigger

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Button/div label. |
| `tag` | literal | `"button"` | `button` or `div` (role="button"). |
| `role` | literal | `""` | `aria-haspopup` value: `menu`, `listbox`, `dialog`, or `""`. |
| `behavior` | `bool` | `True` | When `True`, adds `data-pjx-toggle`. |

### PJXPopoverPanel

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Panel body. |
| `as_form` | `bool` | `False` | Render panel as `<form>` instead of `<div>`. |
| `role` | literal | `""` | ARIA `role` attribute (`menu`, `listbox`, `dialog`, or `""`). |
| `behavior` | `bool` | `True` | When `True`, adds `data-pjx-popover-panel` (hidden by default). |

**DOM contract.** Root `[data-pjx-popover]` (the PJXPopover wrapper). Trigger: `[data-pjx-toggle]` on the trigger element; `aria-expanded` synced by JS. Panel: `[data-pjx-popover-panel]` element, `hidden` when closed. `data-pjx-close` inside the panel closes it. `data-pjx-toggle="<panel-id>"` on any element opens/closes a named panel.
Events (bubble from `[data-pjx-popover]`): `pjx:popover:before-open`*, `pjx:popover:open`, `pjx:popover:before-close`*, `pjx:popover:close` — `detail = {reason, trigger}`.
API: `pjx.popover.open(idOrEl)`, `pjx.popover.close(idOrEl)`, `pjx.popover.toggle(idOrEl)`.

**Classes:** `pjx-popover`, `pjx-popover--align-end`, `pjx-popover__trigger`, `pjx-popover__panel`. Theming: see [PJXPopover tokens](#pjxpopover-tokens).

---

## PJXRegionLoader

In-place loading veil over a positioned ancestor. **Assets:** `pjx-region-loader.css`, `pjx-region-loader.js`.

<!-- demo: PJXRegionLoader -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `aria_label` | `str` | `"Loading"` | Accessible label (`role="status"`). |

**Layout:** Overlay is `position: absolute; inset: 0`. Parent must be **`position: relative`** (or any non-`static` value) so coverage is correct.

Supports both declarative (`hx-indicator`) and programmatic use (`pjx.loader.region.*`).

**DOM contract.** Root `.pjx-region-loader` (state: `.pjx-region-loader--visible`, `.pjx-region-loader--hiding`; also responds to `.htmx-request` as an htmx indicator — CSS activates the veil, no JS call required).
Events (non-cancelable): `pjx:region-loader:show`, `pjx:region-loader:hide`.
API: `pjx.loader.region.show/hide/reset(id)` and `pjx.loader.region.wrap(id, promise)`. Ref-counted for concurrent sources: visible from the first `show(id)` to the last `hide(id)`; `show`/`hide` events fire only on real visibility transitions (a show during an in-flight hide cancels it silently); hides finalize via a fallback timer even when animations are disabled. `wrap(id, promise)` pairs show/hide around any async task. Nodes replaced by a swap while sources remain active are re-lit on htmx:afterSettle.

**Classes:** `pjx-region-loader`; state `pjx-region-loader--visible`, `pjx-region-loader--hiding`; `pjx-region-loader__spinner`. Theming: see [PJXRegionLoader tokens](#pjxregionloader-tokens).

---

## PJXTooltip

Composable tooltip shell. Compose with `PJXTooltipTrigger` and `PJXTooltipContent`. **Assets:** `pjx-tooltip.css`, `pjx-tooltip.js` (IIFE — no API, behavior only).

<!-- demo: PJXTooltip -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `placement` | literal | `"top"` | `top`, `bottom`, `start`, `end` → `data-pjx-tooltip-placement`. |
| `content` | `str \| BaseComponent` | `""` | Children: compose `PJXTooltipTrigger` + `PJXTooltipContent` here. |

**DOM contract.** Root `.pjx-tooltip` `<span>`. `data-pjx-tooltip-placement` drives JS positioning. Tip shows on `mouseover` anywhere inside `.pjx-tooltip` root, or on `focusin` of `.pjx-tooltip__trigger`; hides on `mouseout`/`focusout`; repositions on `scroll`. The JS sets `aria-describedby` at runtime when the tip is shown. No JS API (`pjx._tooltipWired` guard only).

**Usage:**

```python
PJXTooltip(
    placement="top",
    content=PJXTooltipTrigger(content="Hover me").render()
    + PJXTooltipContent(content="Helpful tooltip text").render(),
).render()
```

**Classes:** `pjx-tooltip`. Theming: see [PJXTooltip tokens](#pjxtooltip-tokens).

---

## PJXTooltipTrigger

The focusable trigger part of a tooltip. **Assets:** `pjx-tooltip-trigger.css`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Trigger label or element. |

**DOM contract.** `<span class="pjx-tooltip__trigger" tabindex="0">`. The JS sets `aria-describedby` to the tip's id at show time. Place inside a `PJXTooltip` shell.

---

## PJXTooltipContent

The floating tip body. **Assets:** `pjx-tooltip-content.css`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `content` | `str \| BaseComponent` | `""` | Tooltip text or rich content. |

**DOM contract.** `<span class="pjx-tooltip__tip" role="tooltip" hidden>`. The JS removes `hidden` and adds `.pjx-tooltip__tip--visible` on show. Place inside a `PJXTooltip` shell.

---

## PJXAlert

Inline status banner. **Assets:** `pjx_alert.css`, `pjx_alert.js`.

<!-- demo: PJXAlert -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `variant` | literal | `"info"` | `info`, `success`, `warning`, `error` → `pjx-alert--{variant}`. |
| `title` | `str` | `""` | Optional heading. |
| `body` | `str \| BaseComponent` | `""` | Main copy. |
| `dismissible` | `bool` | `False` | When `True`, renders a dismiss button with `data-pjx-close`. |
| `dismiss_label` | `str` | `"Dismiss"` | `aria-label` for the dismiss button. |

**DOM contract.** Root `.pjx-alert` (state: `.pjx-alert--dismissed` — set by JS, hides via `display: none`).
`data-pjx-close` inside triggers dismissal.
Events: `pjx:alert:before-dismiss`* (cancelable), `pjx:alert:dismiss` — `detail = {reason: 'trigger', trigger}`.

**Classes:** `pjx-alert`; variant modifiers `pjx-alert--info`, `--success`, `--warning`, `--error`; dismissed state `pjx-alert--dismissed`; `pjx-alert__inner`, `__text`, `__title`, `__body`, `__dismiss`. Variants use `color-mix` with `--brand`, `--success`, `--warning`, or `--error` / `--error-bg` / `--error-border` where applicable. Theming: see [PJXAlert tokens](#pjxalert-tokens).

---

## PJXDropdown

Button + anchored panel backed by the shared popover engine. **Assets:** `pjx_dropdown.css` only (ships no own JS — `pjx_popover.js` is included via the `js` extra-asset field whenever a PJXDropdown renders).

<!-- demo: PJXDropdown -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `trigger` | `str \| BaseComponent` | `""` | Button label. |
| `items` | `list[str \| BaseComponent]` | `[]` | Menu items rendered inside the panel. |
| `align` | literal | `"start"` | `start` or `end` → `pjx-dropdown--align-end`. |
| `menu_label` | `str` | `"Submenu"` | `aria-label` on the menu panel. |
| `behavior` | `bool` | `True` | When `False`, removes all `data-pjx-*` wiring. |

Trigger id is `{{ id }}-trigger`, menu is `{{ id }}-menu`.

**DOM contract.** Root `.pjx-dropdown` with `data-pjx-popover`. Trigger: `button.pjx-dropdown__trigger` with `data-pjx-toggle="{{ id }}-menu"`, `aria-expanded` synced by `pjx_popover.js`. Panel: `div.pjx-dropdown__menu[data-pjx-popover-panel][role="menu"]`, `hidden` when closed. All popover events and API apply: `pjx.popover.open/close/toggle(panelId)`. Document click outside closes the menu; `Escape` closes all open popovers.

**Classes:** `pjx-dropdown`, `pjx-dropdown--align-end`, `pjx-dropdown__trigger`, `pjx-dropdown__menu`. Theming: see [PJXDropdown tokens](#pjxdropdown-tokens).

---

## PJXDrawer

`<dialog>` shell sheet from an edge. **Assets:** `pjx-drawer.css`, `pjx-drawer.js` (JS stays on the shell; each part ships its own CSS — see [PJXDrawerHeader](#pjxdrawerheader), [PJXDrawerBody](#pjxdrawerbody), [PJXDrawerFooter](#pjxdrawerfooter)).

<!-- demo: PJXDrawer -->

```html
<PJXDrawer id="nav" side="left">
  <PJXDrawerHeader title="Menu"/>
  <PJXDrawerBody>…links…</PJXDrawerBody>
  <PJXDrawerFooter>v1.0</PJXDrawerFooter>
</PJXDrawer>
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `side` | literal | `"right"` | `left`, `right`, or `bottom` → `pjx-drawer--{side}`. |
| `open_on_mount` | `bool` | `False` | Adds `data-pjx-open-on-mount`; JS opens on arrival. |
| `remove_on_close` | `bool` | `False` | Adds `data-pjx-remove-on-close`; JS removes element on close. |
| `class_name` | `str` | `""` | Extra CSS classes on the root `<dialog>`. |
| `content` | `str \| BaseComponent` | `""` | Inner slot; place composable part components here. |

**DOM contract.** Root `dialog.pjx-drawer.pjx-drawer--{side}` (state: `[open]`, `.pjx-drawer--closing`).
`data-pjx-open="<id>"` on any element opens it; `data-pjx-close` inside closes it;
`data-pjx-open-on-mount`, `data-pjx-remove-on-close` reflect lifecycle props.
Events: `pjx:drawer:before-open`*, `pjx:drawer:open`, `pjx:drawer:before-close`*, `pjx:drawer:close` — `*` = cancelable, `detail = {reason, trigger}`, `reason ∈ escape|backdrop|api|trigger`.
API: `pjx.drawer.open(id)`, `pjx.drawer.close(id)`.

**Classes:** `pjx-drawer`; side modifiers `pjx-drawer--left`, `--right`, `--bottom`; closing state `pjx-drawer--closing`. The inner layout classes (`__header`, `__title`, `__close`, `__body`, `__footer`) belong to the part components — see below. Backdrop click closes the dialog (see [intro note](#built-in-ui-components)). Theming: see [PJXDrawer tokens](#pjxdrawer-tokens).

---

## PJXDrawerHeader

Header bar for a `PJXDrawer`. Automatically includes a close button. **Assets:** `pjx-drawer-header.css`.

<!-- demo: PJXDrawerHeader -->

```html
<PJXDrawerHeader title="Menu"/>
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `title` | `str` | `""` | Renders `<span class="pjx-drawer__title">` when set; omit to use `content` for a fully custom header. |
| `close_label` | `str` | `"Close"` | `aria-label` for the auto-included close button. |
| `close_content` | `str` | `"✕"` | Inner HTML/text of the close button. |
| `class_name` | `str` | `""` | Extra CSS classes on the root `<header>`. |
| `content` | `str \| BaseComponent` | `""` | Custom header slot used when `title` is not set. |

**DOM contract.** Root `<header class="pjx-drawer__header">`. When `title` is set renders `<span class="pjx-drawer__title">`. Always renders a `<button class="pjx-drawer__close" data-pjx-close aria-label="...">`.

**Classes:** `pjx-drawer__header`, `pjx-drawer__title`, `pjx-drawer__close`. Theming: see [PJXDrawer tokens](#pjxdrawer-tokens).

---

## PJXDrawerBody

Scrollable body region for a `PJXDrawer`. **Assets:** `pjx-drawer-body.css`.

<!-- demo: PJXDrawerBody -->

```html
<PJXDrawerBody>…links…</PJXDrawerBody>
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `class_name` | `str` | `""` | Extra CSS classes on the root `<div>`. |
| `content` | `str \| BaseComponent` | `""` | Body slot. |

**DOM contract.** Root `<div class="pjx-drawer__body">`.

**Classes:** `pjx-drawer__body`. Theming: see [PJXDrawer tokens](#pjxdrawer-tokens).

---

## PJXDrawerFooter

Footer strip for a `PJXDrawer`. **Assets:** `pjx-drawer-footer.css`.

<!-- demo: PJXDrawerFooter -->

```html
<PJXDrawerFooter>v1.0</PJXDrawerFooter>
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `class_name` | `str` | `""` | Extra CSS classes on the root `<footer>`. |
| `content` | `str \| BaseComponent` | `""` | Footer slot. |

**DOM contract.** Root `<footer class="pjx-drawer__footer">`.

**Classes:** `pjx-drawer__footer`. Theming: see [PJXDrawer tokens](#pjxdrawer-tokens).

---

## PJXProgress

Determinate or indeterminate meter. **Assets:** `pjx_progress.css` only.

<!-- demo: PJXProgress -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `value` | `float \| None` | `None` | Omit or `None` for indeterminate `<progress>`. |
| `max` | `float` | `100` | Passed to `<progress max="…">`. |
| `label` | `str` | `""` | Optional `pjx-progress__label`; wires `aria-labelledby` when set. |
| `loading_label` | `str` | `"Loading"` | `aria-label` fallback on `<progress>` when `label` is empty. |

**DOM contract.** Root `.pjx-progress`; no JS API.

**Classes:** `pjx-progress`, `pjx-progress__label`, `pjx-progress__bar`. Theming: see [PJXProgress tokens](#pjxprogress-tokens).

---

## PJXSkeleton

Placeholder shimmer blocks. **Assets:** `pjx_skeleton.css` only.

<!-- demo: PJXSkeleton -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `variant` | literal | `"text"` | `text` (stacked lines), `circle`, or `rect`. |
| `lines` | `int` | `3` | For `text`, count of `pjx-skeleton__line` rows. |

**DOM contract.** Root `.pjx-skeleton`; no JS API.

**Classes:** `pjx-skeleton`; variant modifiers `pjx-skeleton--text`, `--circle`, `--rect`; `pjx-skeleton__line`, `pjx-skeleton__circle`, `pjx-skeleton__rect`. Theming: see [PJXSkeleton tokens](#pjxskeleton-tokens).

---

## PJXEmptyState

Centered empty view. **Assets:** `pjx-empty-state.css` only (template file **`pjx-empty-state.html`** next to `pjx_empty_state.py`).

<!-- demo: PJXEmptyState -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `image` | `str \| BaseComponent` | `""` | Optional slot above the heading (e.g. illustration markup). |
| `title` | `str` | `""` | Heading (text, escaped). |
| `description` | `str` | `""` | Supporting text (escaped). |
| `action` | `str \| BaseComponent` | `""` | Optional slot (e.g. button markup). |
| `actions` | `list[str \| BaseComponent]` | `[]` | Optional flex row of slots; renders after `action` when both are set. |
| `suggestions` | `list[dict]` | `[]` | Interactive suggestion chips; each dict dispatches a custom event on click. See below. |

**Suggestion chips** (`suggestions`) provide a first-class "click a chip → dispatch an event" pattern — the common use case of filling an input or triggering a quick action without navigation.

Each item in `suggestions` is a dict with:

| Key | Type | Required | Description |
| --- | --- | --- | --- |
| `label` | `str` | yes | Visible chip text. |
| `value` | `str` | no | Value dispatched in the event payload; defaults to `label`. |
| `event` | `str` | no | Custom event name; defaults to `"pjx:suggestion"`. |

The rendered chip uses Alpine's `$dispatch`, so any parent can listen with `@pjx:suggestion.window="..."` (or the custom event name). The dispatched detail is `{ value: "<chip value>" }`.

```python
PJXEmptyState(
    id="chat-empty",
    title="What would you like to do?",
    suggestions=[
        {"label": "Draft a message", "value": "Draft a message"},
        {"label": "Summarise a thread", "event": "fill-input"},
    ],
)
```

```html
<!-- Listener in a parent template -->
<textarea @pjx:suggestion.window="$el.value = $event.detail.value"></textarea>
```

**DOM contract.** Root `.pjx-empty-state`; no JS API (suggestion chips require Alpine for `$dispatch`).

**Classes:** `pjx-empty-state`, `pjx-empty-state__image`, `pjx-empty-state__title`, `pjx-empty-state__desc`, `pjx-empty-state__action`, `pjx-empty-state__actions`, `pjx-empty-state__suggestions`, `pjx-empty-state__chip`. Theming: see [PJXEmptyState tokens](#pjxemptystate-tokens).

---

## PJXLazyPanel

HTMX lazy-load wrapper: a single `div` that fetches `url` on a computed trigger and swaps itself with the response. **Assets:** none.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `url` | `str` | required | Endpoint for the deferred content (`hx-get`). |
| `when` | literal | `"viewport"` | `viewport` (scroll-revealed), `reveal` (`pjx:reveal` from nearest `[data-pjx-region]`), `load` (immediately). Overridden by `trigger`. |
| `trigger` | `str` | `""` | Explicit `hx-trigger` value; overrides `when` entirely when set. |
| `swap` | `str` | `"outerHTML"` | `hx-swap` strategy. |
| `content` | `str \| BaseComponent` | `""` | Placeholder shown until the fetch lands (e.g. a [`PJXSkeleton`](#pjxskeleton)). |

`when` preset mapping:

| `when` | `hx-trigger` value |
| --- | --- |
| `viewport` (default) | `revealed` |
| `reveal` | `pjx:reveal from:closest [data-pjx-region] once` |
| `load` | `load` |

```python
PJXLazyPanel(id="comments", url="/posts/42/comments", content=PJXSkeleton(id="comments-skel"))
```

**DOM contract.** Root `.pjx-lazy-panel`; no JS (pure HTMX). `data-pjx-region` on a PJXPanel or PJXPanelTrigger host fires `pjx:reveal`/`pjx:before-reveal` events that `when="reveal"` listens for.

**Classes:** `pjx-lazy-panel` (unstyled hook). No theming tokens.

---

## PJXDivider

Separator line. **Assets:** `pjx_divider.css` only.

<!-- demo: PJXDivider -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `orientation` | literal | `"horizontal"` | `horizontal` (default `hr`) or `vertical` (bar). |
| `label` | `str` | `""` | If set with horizontal orientation, flex row with label between lines. |

**DOM contract.** Root `.pjx-divider`; no JS API.

**Classes:** `pjx-divider--horizontal`, `pjx-divider--vertical`, `pjx-divider--labeled`, `pjx-divider__line`, `pjx-divider__label`. Theming: see [PJXDivider tokens](#pjxdivider-tokens).

---

## PJXSpinner

Inline loading indicator. **Assets:** `pjx_spinner.css` only.

<!-- demo: PJXSpinner -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `size` | literal | `"md"` | `sm`, `md`, or `lg`. |
| `label` | `str` | `"Loading"` | Visually hidden; exposed to assistive tech. |

**DOM contract.** Root `.pjx-spinner`; no JS API.

**Classes:** `pjx-spinner`, `pjx-spinner--sm|md|lg`, `pjx-spinner__ring`, `pjx-spinner__label` (screen-reader-only). Theming: see [PJXSpinner tokens](#pjxspinner-tokens).

---

## PJXAvatar

Image or initials in a circle. **Assets:** `pjx_avatar.css` only.

<!-- demo: PJXAvatar -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `src` | `str` | `""` | Image URL; when empty, initials fallback is shown. |
| `alt` | `str` | `""` | `img` alt text; also used as `title` on initials. |
| `initials` | `str` | `""` | Up to two characters (trimmed/capped in validation). |
| `size` | `str \| int` | `"md"` | Named token (`sm`, `md`, `lg`) **or** an arbitrary pixel size (`int`) or CSS length string (`"36px"`, `"2.5rem"`). Named tokens emit the BEM modifier class; an int/CSS length renders `width`/`height` inline. |
| `color` | `str` | `""` | Inline `background` color (e.g. `"#4f46e5"`, `"hsl(240 60% 50%)"` ). |

**Arbitrary pixel sizing:** pass an `int` for a pixel size or any CSS length string for a custom size. This bypasses the named-token classes so the avatar can be sized by data rather than the three design-system tokens.

```python
# Named token (emits .pjx-avatar--md)
PJXAvatar(id="a1", initials="AB")

# Pixel size — 36 px circle, no BEM modifier
PJXAvatar(id="a2", initials="AB", size=36)

# Arbitrary CSS length
PJXAvatar(id="a3", initials="AB", size="2.5rem")
```

**DOM contract.** Root `.pjx-avatar`; no JS API.

**Classes:** `pjx-avatar`, `pjx-avatar--sm|md|lg` (named tokens only), `pjx-avatar__img`, `pjx-avatar__initials`. Theming: see [PJXAvatar tokens](#pjxavatar-tokens).

---

## PJXCard

`<article>` shell for composed card layouts. Compose with `PJXCardHeader`, `PJXCardBody`, and `PJXCardFooter` parts. **Assets:** `pjx-card.css` only.

<!-- demo: PJXCard -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `class_name` | `str` | `""` | Extra CSS class(es) on the root element. |
| `content` | `str \| BaseComponent` | `""` | Pre-rendered children (header + body + footer parts). |

```html
<PJXCard>
  <PJXCardHeader title="Q3 report"/>
  <PJXCardBody>Revenue grew 12% over Q1.</PJXCardBody>
  <PJXCardFooter>Updated today</PJXCardFooter>
</PJXCard>
```

**DOM contract.** Root `article.pjx-card`; no JS API.

**Classes:** `pjx-card`. Theming: see [PJXCard tokens](#pjxcard-tokens).

---

## PJXCardHeader

Card header region. When `title` is set it renders `<h3 class="pjx-card__title">` inside the header; when `title` is empty the `content` slot is rendered directly instead. **Assets:** `pjx-card-header.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `title` | `str` | `""` | Convenience shorthand — renders `<h3 class="pjx-card__title">` when set; takes precedence over `content`. |
| `class_name` | `str` | `""` | Extra CSS class(es) on the root element. |
| `content` | `str \| BaseComponent` | `""` | Rich header slot; used when `title` is empty. |

**DOM contract.** Root `header.pjx-card__header`; no JS API.

**Classes:** `pjx-card__header`, `pjx-card__title`. Theming: see [PJXCard tokens](#pjxcard-tokens).

---

## PJXCardBody

Card body region. **Assets:** `pjx-card-body.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `class_name` | `str` | `""` | Extra CSS class(es) on the root element. |
| `content` | `str \| BaseComponent` | `""` | Main card content. |

**DOM contract.** Root `div.pjx-card__body`; no JS API.

**Classes:** `pjx-card__body`. Theming: see [PJXCard tokens](#pjxcard-tokens).

---

## PJXCardFooter

Card footer region. **Assets:** `pjx-card-footer.css` only.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `class_name` | `str` | `""` | Extra CSS class(es) on the root element. |
| `content` | `str \| BaseComponent` | `""` | Footer content (actions, metadata, etc.). |

**DOM contract.** Root `footer.pjx-card__footer`; no JS API.

**Classes:** `pjx-card__footer`. Theming: see [PJXCard tokens](#pjxcard-tokens).

---

## PJXBreadcrumb

Ordered trail of links. **Assets:** `pjx_breadcrumb.css` only.

<!-- demo: PJXBreadcrumb -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `items` | `list[tuple[str, str \| None]]` | `[]` | `(label, href)` left to right; `href` `None` marks the current page. |
| `aria_label` | `str` | `"PJXBreadcrumb"` | `aria-label` on the `<nav>` wrapper. |

`items` may also be passed as a **JSON array** string (e.g. from PascalCase tags): `[["Home","/"],["Here",null]]`.

**DOM contract.** Root `.pjx-breadcrumb`; no JS API.

**Classes:** `pjx-breadcrumb`, `pjx-breadcrumb__list`, `pjx-breadcrumb__item`, `pjx-breadcrumb__link`, `pjx-breadcrumb__current`. Separators via `::after` on items except the last. Theming: see [PJXBreadcrumb tokens](#pjxbreadcrumb-tokens).

---

## PJXTabGroup

Tab buttons and panels. **Assets:** `pjx-tab-group.css`, `pjx-tab-group.js`.

<!-- demo: PJXTabGroup -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `tabs` | `dict[str, str \| BaseComponent]` | `{}` | **Insertion order** is tab order; keys are labels, values are panel bodies. |
| `tabs_label` | `str` | `"Tabs"` | `aria-label` for the tab list. |

`tabs` may also be a **JSON object** string from markup tags (values are HTML strings).

**DOM contract.** Root `.pjx-tab-group` (no `data-pjx-region` on the root). Tab elements: `.pjx-tab-group__tab` (no `data-pjx-panel-key` — tabs match panels by insertion-order index); panel elements: `.pjx-tab-group__panel[data-pjx-region]` (each panel carries `data-pjx-region`). `pjx:before-reveal` (cancelable) fires before switching; `pjx:reveal` fires after; `data-pjx-revealed` is set on the visible panel. `pjx-tab-group.js` delegates `click` document-wide on `.pjx-tab-group__tab` (not scoped to `.pjx-tab-group__list`), updates `aria-selected`, `tabindex`, and `hidden`. On `DOMContentLoaded`, `htmx:afterSwap`, and `htmx:afterSettle`, `pxTabGroupInit` announces the initially visible panel once (`pjx:reveal`, reason `"api"`) so `PJXLazyPanel(when="reveal")` works in default tabs.

**Classes:** `pjx-tab-group`, `pjx-tab-group__list`, `pjx-tab-group__tab`, `pjx-tab-group__panel`. Theming: see [PJXTabGroup tokens](#pjxtabgroup-tokens).

---

## PJXPanel

Host for **distributed** tab-like switching: all bodies render here; controls are separate [`PJXPanelTrigger`](#pjxpaneltrigger) components. **Unstyled** aside from `hidden` panels. **Assets:** `pjx_panel.css`, `pjx_panel.js`.

<!-- demo: PJXPanel -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `panels` | `dict[str, str \| BaseComponent]` | `{}` | **Insertion order** sets the initially visible slot (first is shown). Keys must match `[a-zA-Z0-9_-]+`. |

`panels` may be a **JSON object** string from PascalCase tags. Keys are used in HTML `id` attributes and `data-pjx-panel-key`. Slot element ids are `{{ id }}-panel-{{ key }}`. The `id` must match `PJXPanelTrigger.panel_id`.

**DOM contract.** Root `.pjx-panel` with `id`. Panels: `.pjx-panel__panel[data-pjx-panel-key][data-pjx-region]`. Events (bubble from the active panel): `pjx:before-reveal`* (cancelable, `detail = {reason, trigger}`), `pjx:reveal`; `data-pjx-revealed` on the visible panel. `pjx_panel.js` click delegation on `.pjx-panel-trigger`; `pxPanelInit` runs on `DOMContentLoaded`, `htmx:afterSwap`, `htmx:afterSettle`.

**Classes:** `pjx-panel`, `pjx-panel__panel`. No theme tokens; minimal rules for `[hidden]` panels.

---

## PJXPanelTrigger

Invisible wrapper that wires clicks to a [`PJXPanel`](#pjxpanel) slot. **Assets:** `pjx-panel-trigger.css`. See the [`pjx_panel.js` loading note](#built-in-ui-components)—render a `PJXPanel` on the same page so the script is included.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `panel_id` | `str` | (required) | Must equal the target `PJXPanel.id`. |
| `panel` | `str` | (required) | Key matching a key in `PJXPanel.panels`; `[a-zA-Z0-9_-]+`. |
| `content` | `str \| BaseComponent` | `""` | Inner HTML / nested components (your visible control). |

Maps children to `content`; see the [children-vs-`content` note](#built-in-ui-components).

**DOM contract.** Root `.pjx-panel-trigger[data-pjx-panel-id][data-pjx-panel-key]`; no own JS (wired by `pjx_panel.js`). `display: contents` so no layout box. On every panel switch, `pjx_panel.js` syncs `aria-selected` and `tabindex` on every `.pjx-panel-trigger[data-pjx-panel-id]` matching the host PJXPanel.

**Classes:** `pjx-panel-trigger`. No theming tokens.

---

## PJXConfirmDialog

Accessible `<dialog>` singleton that replaces `window.confirm`. Mount once in the layout; `pjx.confirm()` is available everywhere. **Assets:** `pjx-confirm-dialog.css`, `pjx-confirm-dialog.js`.

<!-- demo: PJXConfirmDialog -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `confirm_label` | `str` | `"Confirm"` | Default OK button text. |
| `cancel_label` | `str` | `"Cancel"` | Default cancel button text. |

```python
PJXConfirmDialog(id="app-confirm")
```

Intercepts every `hx-confirm="…"` automatically (via `htmx:confirm` event):

```html
<button hx-post="/delete/1"
        hx-confirm="Delete this item?"
        data-pjx-confirm-danger>Delete</button>
```

For non-htmx forms use `data-confirm="…"` on the `<form>`.

Override labels per-call:

```javascript
const ok = await pjx.confirm("Are you sure?", {
    okLabel: "Yes, delete",
    cancelLabel: "No",
    danger: true,
});
if (ok) { /* proceed */ }
```

**DOM contract.** Root `dialog.pjx-confirm-dialog[data-pjx-dialog="confirm"]` — singleton, matched by `document.querySelector`. `data-pjx-confirm-danger` on the htmx element → OK button gets `.pjx-confirm-dialog__ok--danger`. `data-pjx-confirm-ok` / `data-pjx-confirm-cancel` per-trigger label overrides.
API: `pjx.confirm(message, {okLabel?, cancelLabel?, danger?}) → Promise<boolean>`.
Falls back to `window.confirm` if no `PJXConfirmDialog` is mounted.

**Classes:** `pjx-confirm-dialog`, `pjx-confirm-dialog__card`, `pjx-confirm-dialog__message`, `pjx-confirm-dialog__actions`, `pjx-confirm-dialog__ok`, `pjx-confirm-dialog__ok--danger`, `pjx-confirm-dialog__cancel`. Theming: see [PJXConfirmDialog tokens](#pjxconfirmdialog-tokens).

---

## PJXPromptDialog

Accessible `<dialog>` singleton that replaces `window.prompt`. Mount once in the layout; `pjx.prompt()` is available everywhere. **Assets:** `pjx-prompt-dialog.css`, `pjx-prompt-dialog.js`.

<!-- demo: PJXPromptDialog -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `input_label` | `str` | `""` | Default label text above the input. |
| `submit_label` | `str` | `"OK"` | Submit button text. |
| `cancel_label` | `str` | `"Cancel"` | Cancel button text. |

```python
PJXPromptDialog(id="app-prompt")
```

```javascript
const name = await pjx.prompt("Enter your name", {
    initial: "Alice",
    placeholder: "Full name",
    okLabel: "Save",
});
if (name !== null) { /* user submitted */ }
```

**DOM contract.** Root `dialog.pjx-prompt-dialog[data-pjx-dialog="prompt"]` — singleton, matched by `document.querySelector`. Input pre-focused and selected on open.
API: `pjx.prompt(title, {initial?, placeholder?, okLabel?, cancelLabel?}) → Promise<string | null>`.
Returns `null` on cancel/Escape/backdrop close. Falls back to `window.prompt` if no `PJXPromptDialog` is mounted.

**Classes:** `pjx-prompt-dialog`, `pjx-prompt-dialog__card`, `pjx-prompt-dialog__label`, `pjx-prompt-dialog__input`, `pjx-prompt-dialog__actions`, `pjx-prompt-dialog__ok`, `pjx-prompt-dialog__cancel`. Theming: see [PJXPromptDialog tokens](#pjxpromptdialog-tokens).

---

## PJXToastHost

HX-Trigger-driven toast container singleton. Mount once in the layout. **Assets:** `pjx-toast-host.css`, `pjx-toast-host.js`.

<!-- demo: PJXToastHost -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `position` | literal | `"bottom-right"` | `top-right`, `top-left`, `bottom-right`, `bottom-left`. |
| `timeout` | `int` | `4000` | Default auto-dismiss ms; `0` disables. |
| `dismiss_label` | `str` | `"Dismiss"` | `aria-label` for dismiss buttons on individual toasts. |
| `event_name` | `str` | `"pjx:toast"` | Custom event name to listen for (wired on mount). |

```python
PJXToastHost(id="app-toasts", position="top-right")
```

Fire from a FastAPI route via `HX-Trigger`:

```python
import json

response.headers["HX-Trigger"] = json.dumps({"pjx:toast": {"message": "Saved.", "level": "success"}})
```

Or from JS:

```javascript
pjx.toast("Upload complete.", { level: "success", timeout: 3000 });
```

Toast `level` maps to `.pjx-toast--<level>`; supported values: `info`, `success`, `warning`, `error`.

**DOM contract.** Root `div.pjx-toast-host[data-pjx-toast-host]`. `data-event-name` sets the custom event; `data-timeout` sets the default dismiss timeout; `data-dismiss-label` sets dismiss button label.
Events (bubble from the host): `pjx:toasthost:show` (detail: `{level}`), `pjx:toasthost:hide`.
API: `pjx.toast(message, {level?, timeout?})`.
Individual toasts: `div.pjx-toast.pjx-toast--<level>` > `.pjx-toast__message` + `button.pjx-toast__dismiss`.

**Classes:** `pjx-toast-host`, `pjx-toast-host--top-right`, `--top-left`, `--bottom-right`, `--bottom-left`; `pjx-toast`, `pjx-toast--info`, `--success`, `--warning`, `--error`; `pjx-toast--hiding`; `pjx-toast__message`, `pjx-toast__dismiss`. Theming: see [PJXToastHost tokens](#pjxtoasthost-tokens).

---

## PJXAvatarStack

Overlapping row of avatars with optional overflow count. **Assets:** `pjx-avatar-stack.css` only.

<!-- demo: PJXAvatarStack -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `avatars` | `list[dict \| str \| BaseComponent]` | `[]` | Per-avatar items — see below for the two accepted shapes. |
| `extra_count` | `int` | `0` | When `> 0`, renders a `+N` overflow chip. |
| `empty_label` | `str` | `""` | When no avatars and `empty_label` is set, renders a fallback label. |

**Two item shapes are accepted in `avatars`:**

1. **Structured data dict** — the stack renders its own pill; no child `PJXAvatar` needed.

   | Key | Type | Required | Description |
   | --- | --- | --- | --- |
   | `initials` | `str` | yes | Up to two characters shown in the pill. |
   | `color` | `str` | no | Inline `background` color. |
   | `alt` | `str` | no | `title` tooltip (takes precedence over `name`). |
   | `name` | `str` | no | Fallback tooltip when `alt` is not set. |

2. **Pre-built item** — an HTML string or any `BaseComponent` instance (original interface, still fully supported).

```python
# Structured data — stack owns rendering; no PJXAvatar required
PJXAvatarStack(
    id="team",
    avatars=[
        {"initials": "AB", "color": "#4f46e5", "name": "Alice"},
        {"initials": "CD", "color": "#16a34a", "name": "Charlie"},
    ],
    extra_count=3,
)

# Pre-built components (original interface)
PJXAvatarStack(
    id="team",
    avatars=[
        PJXAvatar(id="a1", initials="AB", size="sm"),
        PJXAvatar(id="a2", initials="CD", size="sm"),
    ],
    extra_count=3,
)
```

**DOM contract.** Root `.pjx-avatar-stack`; no JS API.

**Classes:** `pjx-avatar-stack`, `pjx-avatar-stack__pill` (dict-rendered pills), `pjx-avatar-stack__more`, `pjx-avatar-stack__empty`. Theming: see [PJXAvatarStack tokens](#pjxavatarstack-tokens).

---

## PJXPageLoader

Full-page navigation loader. Mount once at the top of the layout body. **Assets:** `pjx-page-loader.css`, `pjx-page-loader.js`.

<!-- demo: PJXPageLoader -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `nav_targets` | `str` | `"app-content"` | Comma-separated element ids whose htmx GET requests activate the loader. |
| `active_on_load` | `bool` | `True` | When `True`, renders with `.pjx-page-loader--active` (cold-load shimmer, removed on `DOMContentLoaded`). |
| `loading_label` | `str` | `"Loading"` | `aria-label` for the `role="status"` element. |

```python
PJXPageLoader(id="page-loader", nav_targets="main-content,sidebar")
```

Add `data-pjx-loader` to any element to make its htmx requests activate the loader regardless of `nav_targets`:

```html
<a hx-get="/slow-page" hx-target="#main-content" data-pjx-loader>Go</a>
```

**DOM contract.** Root `div.pjx-page-loader[data-pjx-page-loader]` (state: `.pjx-page-loader--active`).
`data-nav-targets` — comma-separated ids; htmx GET requests targeting any of these activate the loader.
`data-pjx-loader` on any element marks its htmx requests as loader-tracked regardless of target.
Tracking is detected via `htmx:beforeRequest`; the loader releases via the request's `loadend` (terminal on load, error, abort, and timeout); history navigations reset via `htmx:historyRestore`.
Events (non-cancelable, bubble from the root): `pjx:page-loader:show`, `pjx:page-loader:hide`.
API: `pjx.loader.page.show()`, `pjx.loader.page.hide()`, `pjx.loader.page.reset()`, `pjx.loader.page.wrap(promise)`.

**Classes:** `pjx-page-loader`, `pjx-page-loader--active`, `pjx-page-loader__spinner`. Theming: see [PJXPageLoader tokens](#pjxpageloader-tokens).

---

## Form controls

---

## PJXChipInput

Tag-style multi-value input. Each chip carries its own `<input type="hidden">` so values post with any enclosing form and removal is pure DOM removal. **Assets:** `pjx-chip-input.css`, `pjx-chip-input.js`.

<!-- demo: PJXChipInput -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `str` | — | `name` attribute on the hidden inputs and the `data-name` data attribute. |
| `values` | `list[str]` | `[]` | Initial chip values. |
| `placeholder` | `str` | `"Add…"` | Placeholder text in the text field. |
| `remove_label` | `str` | `"Remove"` | `aria-label` on every remove button; also stored as `data-remove-label` so JS can copy it into dynamically built chips. |
| `disabled` | `bool` | `False` | When `True`, no text field or remove buttons are rendered; `data-disabled` is set on the root. |

```python
PJXChipInput(id="tags", name="tags", values=["python", "jinja2"], placeholder="Add tag…")
```

**DOM contract.** Root `div.pjx-chip-input[data-pjx-chip-input][data-name][data-remove-label]`; state: `[data-disabled]`.
Each chip: `span.pjx-chip-input__chip[data-pjx-chip]` containing a `.pjx-chip-input__label`, `input[type=hidden]`, and (when enabled) `button.pjx-chip-input__remove[data-pjx-chip-remove]`.
Text field: `input.pjx-chip-input__field`.
Events (bubble from root): `pjx:chip-input:before-add`* (detail `{value}`), `pjx:chip-input:add`, `pjx:chip-input:before-remove`* (detail `{value}`), `pjx:chip-input:remove` — `*` = cancelable. Commit triggers: `Enter`, `,`, `focusout`, `submit` (form submit commits pending text); Backspace on empty field removes the last chip.

**Classes:** `pjx-chip-input`, `pjx-chip-input__chip`, `pjx-chip-input__label`, `pjx-chip-input__remove`, `pjx-chip-input__field`. Theming: see [PJXChipInput tokens](#pjxchipinput-tokens).

**Notes:**

- `values` are plain-text chip labels and are **HTML-escaped** on render (output is escaped by default — see [Escaping & slots](components.md#escaping-and-slots)). Passing markup shows it as literal text, not HTML.
- Duplicate entries are silently dropped (the field clears).
- Chips added client-side exist only in the DOM until the form posts; an htmx swap of the surrounding region re-renders from server state.

---

## PJXFormField

Labelled control wrapper with help text and error state. **Assets:** `pjx-form-field.css` only.

<!-- demo: PJXFormField -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `label` | `str` | `""` | Label text; renders `<label>` only when non-empty. |
| `for_id` | `str` | `""` | When set, adds `for="{{ for_id }}"` to the label. |
| `content` | `str \| BaseComponent` | `""` | Control HTML (an `<input>`, `<select>`, etc.). |
| `help` | `str` | `""` | Help text shown below the control — suppressed when `error` is set. |
| `error` | `str` | `""` | Error message; adds `pjx-form-field--error` to the root and a `role="alert"` paragraph with id `{{ id }}-error`. |
| `required` | `bool` | `False` | Renders a `<span class="pjx-form-field__required" aria-hidden="true">*</span>` inside the label. |

```python
PJXFormField(
    id="email-field",
    label="Email",
    for_id="email-input",
    content='<input id="email-input" type="email" name="email">',
    error="Please enter a valid email address.",
    required=True,
)
```

**DOM contract.** Root `div.pjx-form-field`; error state `div.pjx-form-field--error`. Help paragraph id: `{{ id }}-help`. Error paragraph id: `{{ id }}-error`, `role="alert"`. No JS.

**Classes:** `pjx-form-field`, `pjx-form-field--error`, `pjx-form-field__label`, `pjx-form-field__required`, `pjx-form-field__control`, `pjx-form-field__help`, `pjx-form-field__error`. Theming: see [PJXFormField tokens](#pjxformfield-tokens).

---

## PJXToggleSwitch

Accessible on/off toggle backed by a visually-hidden checkbox. **Assets:** `pjx-toggle-switch.css` only — no JS.

<!-- demo: PJXToggleSwitch -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `str` | `""` | `name` attribute on the hidden checkbox. |
| `value` | `str` | `"on"` | `value` attribute on the checkbox. |
| `checked` | `bool` | `False` | When `True`, adds `checked` to the checkbox. |
| `label` | `str` | `""` | Visible label text rendered after the track; omitted when empty. |
| `disabled` | `bool` | `False` | When `True`, adds `disabled` to the checkbox. |

```python
PJXToggleSwitch(id="dark-mode", name="dark_mode", checked=True, label="Dark mode")
```

**DOM contract.** Root `label.pjx-toggle-switch` wrapping a visually-hidden `input[type=checkbox].pjx-toggle-switch__input` (uses `clip-path: inset(50%)`, not `display:none` — keeps focus and click). CSS keys on `:checked + .pjx-toggle-switch__track` for the active state and `:focus-visible + .pjx-toggle-switch__track` for the ring. No JS API.

**Classes:** `pjx-toggle-switch`, `pjx-toggle-switch__input`, `pjx-toggle-switch__track`, `pjx-toggle-switch__thumb`, `pjx-toggle-switch__label`. Theming: see [PJXToggleSwitch tokens](#pjxtoggleswitch-tokens).

---

## PJXSegmentedControl

Pill-style radio group for mutually exclusive options. **Assets:** `pjx-segmented-control.css` only — no JS.

<!-- demo: PJXSegmentedControl -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `str` | — | `name` on all radio inputs. |
| `options` | `list[tuple[str, str]]` | `[]` | `(value, label)` pairs. Also accepts a JSON string when passed as a tag attribute. |
| `selected` | `str` | `""` | Value of the pre-checked option. |
| `disabled` | `bool` | `False` | When `True`, adds `disabled` to all radio inputs. |

```python
PJXSegmentedControl(
    id="view-switcher",
    name="view",
    options=[("list", "List"), ("grid", "Grid"), ("table", "Table")],
    selected="list",
)
```

**DOM contract.** Root `div.pjx-segmented-control[role="radiogroup"]`. Each option: `label.pjx-segmented-control__segment` > `input[type=radio].pjx-segmented-control__input` (visually hidden, `clip-path: inset(50%)`) + `span.pjx-segmented-control__text`. CSS keys on `:checked + .pjx-segmented-control__text` for the active segment. No JS API.

**Classes:** `pjx-segmented-control`, `pjx-segmented-control__segment`, `pjx-segmented-control__input`, `pjx-segmented-control__text`. Theming: see [PJXSegmentedControl tokens](#pjxsegmentedcontrol-tokens).

---

## PJXPasswordInput

Password field with a show/hide toggle button. **Assets:** `pjx-password-input.css`, `pjx-password-input.js`.

<!-- demo: PJXPasswordInput -->

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `str` | `"password"` | `name` on the `<input>`. |
| `placeholder` | `str` | `""` | `placeholder` on the `<input>`; omitted when empty. |
| `autocomplete` | `str` | `"current-password"` | `autocomplete` attribute. |
| `required` | `bool` | `False` | When `True`, adds `required` to the `<input>`. |
| `show_label` | `str` | `"Show password"` | Static `aria-label` on the toggle button; visibility state is conveyed by `aria-pressed` (ARIA toggle-button pattern). |

```python
PJXPasswordInput(id="login-pw", autocomplete="current-password", required=True)
```

**DOM contract.** Root `div.pjx-password-input[data-pjx-password]`. Field: `input.pjx-password-input__field` with id `{{ id }}-field`. Toggle button: `button.pjx-password-input__toggle[data-pjx-password-toggle]`; `aria-pressed` reflects state (`"false"` when hidden, `"true"` when shown); `.pjx-password-input__toggle--on` class added when visible. No `pjx:*` events — state is readable from `aria-pressed` on the button. No JS API under `window.pjx`.

**Classes:** `pjx-password-input`, `pjx-password-input__field`, `pjx-password-input__toggle`, `pjx-password-input__toggle--on`, `pjx-password-input__eye`. Theming: see [PJXPasswordInput tokens](#pjxpasswordinput-tokens).

---

## Example

```python
from pyjinhx.builtins import (
    PJXAvatarStack,
    PJXBadge,
    PJXBreadcrumb,
    PJXCard,
    PJXCardBody,
    PJXCardFooter,
    PJXCardHeader,
    PJXConfirmDialog,
    PJXDrawer,
    PJXModal,
    PJXNotification,
    PJXPageLoader,
    PJXPanel,
    PJXPanelTrigger,
    PJXTabGroup,
    PJXToastHost,
    PJXTooltip,
    PJXTooltipContent,
    PJXTooltipTrigger,
)

badge = PJXBadge(id="status-badge", label="Beta", color="brand")
modal = PJXModal(
    id="info-modal",
    content=(
        PJXModalHeader(title="Hello").render()
        + PJXModalBody(content="Content here.").render()
    ),
)
toast = PJXNotification(id="welcome-toast", content="Saved.", corner="bottom-right", timeout=3000)
drawer = PJXDrawer(id="filters", side="right", content=(
    PJXDrawerHeader(title="Filters").render()
    + PJXDrawerBody(content="…").render()
))
tip = PJXTooltip(
    id="help-tip",
    placement="top",
    content=PJXTooltipTrigger(id="help-tip-tr", content="?").render()
    + PJXTooltipContent(id="help-tip-tc", content="More detail").render(),
)
card = PJXCard(id="summary", content=PJXCardHeader(title="Summary").render() + PJXCardBody(content="Details go here.").render() + PJXCardFooter(content="Last updated today.").render())
crumb = PJXBreadcrumb(id="crumb", items=[("App", "/"), ("Page", None)])
tabs = PJXTabGroup(
    id="main-tabs",
    tabs={"A": "<p>First</p>", "B": "<p>Second</p>"},
)
main_panel = PJXPanel(
    id="app-panels",
    panels={"chat": "<p>Chat UI</p>", "other": "<p>Other</p>"},
)
open_chat = PJXPanelTrigger(
    id="open-chat", panel_id="app-panels", panel="chat", content="Chat"
)
confirm = PJXConfirmDialog(id="app-confirm")
toasts = PJXToastHost(id="app-toasts", position="bottom-right")
page_loader = PJXPageLoader(id="page-loader")
avatar_stack = PJXAvatarStack(id="team", avatars=[], extra_count=5)
```

---

## Theming tokens

Per-component `--pjx-*` custom properties and their default mappings. Override any token in your own CSS.

### PJXBadge tokens

| Token | Default (maps to) |
| --- | --- |
| `--pjx-badge-font-size` | `var(--font-size-xs)` |
| `--pjx-badge-radius-sm` | `var(--radius-sm)` |
| `--pjx-badge-radius-md` | `var(--radius-md)` |
| `--pjx-badge-radius-full` | `var(--radius-full)` |
| `--pjx-badge-brand-bg` | `var(--brand-subtle)` |
| `--pjx-badge-brand-fg` | `var(--brand-muted)` |
| `--pjx-badge-brand-accent` | `var(--brand)` |
| `--pjx-badge-error-bg` | `var(--error-bg)` |
| `--pjx-badge-error-fg` | `var(--error)` |
| `--pjx-badge-error-border` | `var(--error-border)` |
| `--pjx-badge-neutral-bg` | `var(--surface-alt)` |
| `--pjx-badge-neutral-fg` | `var(--text)` |
| `--pjx-badge-neutral-border` | `var(--border)` |
| `--pjx-badge-muted-bg` | `var(--surface)` |
| `--pjx-badge-muted-fg` | `var(--text-muted)` |
| `--pjx-badge-muted-border` | `var(--border)` |

### PJXButton tokens

| Token | Default |
| --- | --- |
| `--pjx-button-bg` | `transparent` |
| `--pjx-button-color` | `inherit` |
| `--pjx-button-border` | `1px solid currentColor` |
| `--pjx-button-radius` | `0.375rem` |
| `--pjx-button-padding` | `0.5rem 0.875rem` |
| `--pjx-button-gap` | `0.5rem` |
| `--pjx-button-font-size` | `inherit` |
| `--pjx-button-font-weight` | `500` |
| `--pjx-button-bg-hover` | `var(--pjx-button-bg)` |
| `--pjx-button-border-hover` | `currentColor` |

### PJXAccordion tokens

| Token | Default |
| --- | --- |
| `--pjx-accordion-radius` | `0` |
| `--pjx-accordion-trigger-bg` | `transparent` |
| `--pjx-accordion-trigger-color` | `inherit` |
| `--pjx-accordion-trigger-padding` | `0.5rem 0.75rem` |
| `--pjx-accordion-trigger-font-size` | `inherit` |
| `--pjx-accordion-trigger-font-weight` | `500` |
| `--pjx-accordion-trigger-bg-hover` | `var(--pjx-accordion-trigger-bg)` |
| `--pjx-accordion-chevron-size` | `1em` |

### PJXAccordionGroup tokens

| Token | Default |
| --- | --- |
| `--pjx-accordion-group-gap` | `0` |

### PJXModal tokens

| Token | Default |
| --- | --- |
| `--pjx-modal-width` | `52rem` |
| `--pjx-modal-min-height` | `28rem` |
| `--pjx-modal-bg` | `var(--surface)` |
| `--pjx-modal-border` | `var(--border)` |
| `--pjx-modal-radius` | `var(--radius-lg)` |
| `--pjx-modal-shadow` | `var(--shadow-md)` |
| `--pjx-modal-header-bg` | `var(--surface-alt)` |
| `--pjx-modal-header-sep` | `var(--border)` |
| `--pjx-modal-footer-bg` | `var(--surface-alt)` |
| `--pjx-modal-footer-sep` | `var(--border)` |
| `--pjx-modal-title-color` | `var(--text)` |
| `--pjx-modal-close-color` | `var(--text-muted)` |
| `--pjx-modal-backdrop` | `rgb(0 0 0 / 0.6)` |
| `--pjx-modal-padding` | `1.5rem` |

Close control hover uses `var(--surface)`, `var(--text)`, `var(--radius-sm)`, `var(--transition)` from your theme.

### PJXNotification tokens

| Token | Default |
| --- | --- |
| `--pjx-notification-width` | `22rem` |
| `--pjx-notification-gap` | `1.25rem` (viewport inset; used in slide animations) |
| `--pjx-notification-bg` | `var(--surface-alt)` |
| `--pjx-notification-border` | `var(--border)` |
| `--pjx-notification-radius` | `var(--radius-md)` |
| `--pjx-notification-shadow` | `var(--shadow-md)` |
| `--pjx-notification-padding` | `1rem 1rem 1rem 1.25rem` |
| `--pjx-notification-close-color` | `var(--text-muted)` |
| `--pjx-notification-z` | `500` |

Content uses `var(--font-size-sm)`, `var(--text)`; close hover uses `var(--surface)`, `var(--text)`, `var(--radius-sm)`, `var(--transition)`.

### PJXPopover tokens

| Token | Default |
| --- | --- |
| `--pjx-popover-max-width` | `28ch` |
| `--pjx-popover-bg` | `var(--surface-alt)` |
| `--pjx-popover-border` | `var(--border)` |
| `--pjx-popover-radius` | `var(--radius-md)` |
| `--pjx-popover-shadow` | `var(--shadow-md)` |
| `--pjx-popover-padding` | `var(--space-3, 0.75rem) var(--space-4, 1rem)` |
| `--pjx-popover-z` | `300` |

### PJXRegionLoader tokens

| Token | Default |
| --- | --- |
| `--pjx-region-loader-bg` | `rgb(0 0 0 / 0.55)` |
| `--pjx-region-loader-backdrop` | `blur(2px)` |
| `--pjx-region-loader-z` | `100` |
| `--pjx-region-loader-spinner-size` | `2.5rem` |
| `--pjx-region-loader-spinner-width` | `3px` |
| `--pjx-region-loader-spinner-color` | `var(--brand)` |
| `--pjx-region-loader-spinner-track` | `rgb(255 255 255 / 0.1)` |

### PJXTooltip tokens

| Token | Default |
| --- | --- |
| `--pjx-tooltip-gap` | `6px` |
| `--pjx-tooltip-bg` | `var(--surface-alt)` |
| `--pjx-tooltip-border` | `var(--border)` |
| `--pjx-tooltip-radius` | `var(--radius-sm)` |
| `--pjx-tooltip-shadow` | `var(--shadow-md)` |
| `--pjx-tooltip-padding` | `0.35rem 0.5rem` |
| `--pjx-tooltip-max-width` | `20ch` |
| `--pjx-tooltip-fg` | `var(--text)` |
| `--pjx-tooltip-font-size` | `var(--font-size-xs)` |
| `--pjx-tooltip-z` | `400` |

### PJXAlert tokens

| Token | Default |
| --- | --- |
| `--pjx-alert-radius` | `var(--radius-md)` |
| `--pjx-alert-padding` | `0.875rem 1rem` |
| `--pjx-alert-border` | `var(--border)` |
| `--pjx-alert-shadow` | `var(--shadow-md)` |
| `--pjx-alert-title-size` | `var(--font-size-sm)` |
| `--pjx-alert-body-size` | `var(--font-size-sm)` |
| `--pjx-alert-dismiss-color` | `var(--text-muted)` |

### PJXDropdown tokens

| Token | Default |
| --- | --- |
| `--pjx-dropdown-menu-bg` | `var(--surface-alt)` |
| `--pjx-dropdown-menu-border` | `var(--border)` |
| `--pjx-dropdown-menu-radius` | `var(--radius-md)` |
| `--pjx-dropdown-menu-shadow` | `var(--shadow-md)` |
| `--pjx-dropdown-menu-padding` | `0.35rem 0` |
| `--pjx-dropdown-menu-min-w` | `10rem` |
| `--pjx-dropdown-menu-max-h` | `min(70dvh, 24rem)` |
| `--pjx-dropdown-z` | `350` |

### PJXDrawer tokens

| Token | Default |
| --- | --- |
| `--pjx-drawer-width` | `min(24rem, 100vw)` |
| `--pjx-drawer-height-bottom` | `min(50dvh, 28rem)` |
| `--pjx-drawer-bg` | `var(--surface)` |
| `--pjx-drawer-border` | `var(--border)` |
| `--pjx-drawer-shadow` | `var(--shadow-md)` |
| `--pjx-drawer-backdrop` | `rgb(0 0 0 / 0.45)` |
| `--pjx-drawer-header-bg` | `var(--surface-alt)` |
| `--pjx-drawer-header-sep` | `var(--border)` |
| `--pjx-drawer-footer-bg` | `var(--surface-alt)` |
| `--pjx-drawer-footer-sep` | `var(--border)` |
| `--pjx-drawer-padding` | `1rem` |
| `--pjx-drawer-z` | `250` |

### PJXProgress tokens

| Token | Default |
| --- | --- |
| `--pjx-progress-height` | `0.5rem` |
| `--pjx-progress-radius` | `var(--radius-full)` |
| `--pjx-progress-track` | `var(--surface-alt)` |
| `--pjx-progress-fill` | `var(--brand)` |
| `--pjx-progress-indeterminate-speed` | `1.2s` |

### PJXSkeleton tokens

| Token | Default |
| --- | --- |
| `--pjx-skeleton-bg` | `var(--surface-alt)` |
| `--pjx-skeleton-shine` | `color-mix(in srgb, var(--text) 8%, var(--surface-alt))` |
| `--pjx-skeleton-line-height` | `0.65rem` |
| `--pjx-skeleton-line-gap` | `0.5rem` |
| `--pjx-skeleton-circle-size` | `2.5rem` |
| `--pjx-skeleton-rect-height` | `6rem` |
| `--pjx-skeleton-rect-radius` | `var(--radius-md)` |
| `--pjx-skeleton-duration` | `1.2s` |

### PJXEmptyState tokens

| Token | Default |
| --- | --- |
| `--pjx-empty-state-padding` | `2rem 1.5rem` |
| `--pjx-empty-state-max-width` | `28rem` |
| `--pjx-empty-state-title-size` | `var(--font-size-md)` |
| `--pjx-empty-state-desc-size` | `var(--font-size-sm)` |
| `--pjx-empty-state-title-color` | `var(--text)` |
| `--pjx-empty-state-desc-color` | `var(--text-muted)` |
| `--pjx-empty-state-gap` | `0.5rem` |
| `--pjx-empty-state-actions-gap` | `0.5rem` |

### PJXDivider tokens

| Token | Default |
| --- | --- |
| `--pjx-divider-color` | `var(--border)` |
| `--pjx-divider-thickness` | `1px` |
| `--pjx-divider-gap` | `0.75rem` |
| `--pjx-divider-label-color` | `var(--text-muted)` |
| `--pjx-divider-label-size` | `var(--font-size-sm)` |

### PJXSpinner tokens

| Token | Default |
| --- | --- |
| `--pjx-spinner-sm` | `1.25rem` |
| `--pjx-spinner-md` | `2rem` |
| `--pjx-spinner-lg` | `2.75rem` |
| `--pjx-spinner-track` | `color-mix(in srgb, var(--text-muted) 35%, transparent)` |
| `--pjx-spinner-accent` | `var(--brand)` |

### PJXAvatar tokens

| Token | Default |
| --- | --- |
| `--pjx-avatar-sm` | `2rem` |
| `--pjx-avatar-md` | `2.5rem` |
| `--pjx-avatar-lg` | `3.25rem` |
| `--pjx-avatar-bg` | `var(--surface-alt)` |
| `--pjx-avatar-fg` | `var(--text-muted)` |
| `--pjx-avatar-border` | `var(--border)` |

### PJXCard tokens

| Token | Default |
| --- | --- |
| `--pjx-card-bg` | `var(--surface-alt)` |
| `--pjx-card-border` | `var(--border)` |
| `--pjx-card-radius` | `var(--radius-md)` |
| `--pjx-card-title-color` | `var(--text)` |
| `--pjx-card-padding` | `var(--space-4, 1rem)` |

### PJXBreadcrumb tokens

| Token | Default |
| --- | --- |
| `--pjx-breadcrumb-sep` | `"/"` |
| `--pjx-breadcrumb-link-color` | `var(--brand)` |
| `--pjx-breadcrumb-current-color` | `var(--text)` |

### PJXTabGroup tokens

| Token | Default |
| --- | --- |
| `--pjx-tab-group-border` | `var(--border)` |
| `--pjx-tab-group-bg` | `var(--surface-alt)` |
| `--pjx-tab-group-tab-active-fg` | `var(--text)` |
| `--pjx-tab-group-tab-active-bg` | `color-mix(in srgb, var(--surface) 55%, var(--surface-alt))` |
| `--pjx-tab-group-tab-active-border` | `var(--brand)` |
| `--pjx-tab-group-panel-bg` | `var(--surface)` |

### PJXConfirmDialog tokens

| Token | Default |
| --- | --- |
| `--pjx-confirm-dialog-bg` | `var(--surface)` |
| `--pjx-confirm-dialog-border` | `var(--border)` |
| `--pjx-confirm-dialog-radius` | `var(--radius-md)` |
| `--pjx-confirm-dialog-shadow` | `var(--shadow-md)` |
| `--pjx-confirm-dialog-backdrop` | `rgb(0 0 0 / 0.5)` |
| `--pjx-confirm-dialog-danger` | `#b3261e` |

### PJXPromptDialog tokens

| Token | Default |
| --- | --- |
| `--pjx-prompt-dialog-bg` | `var(--surface)` |
| `--pjx-prompt-dialog-border` | `var(--border)` |
| `--pjx-prompt-dialog-radius` | `var(--radius-md)` |
| `--pjx-prompt-dialog-shadow` | `var(--shadow-md)` |
| `--pjx-prompt-dialog-backdrop` | `rgb(0 0 0 / 0.5)` |

### PJXToastHost tokens

| Token | Default |
| --- | --- |
| `--pjx-toast-bg` | `var(--surface)` |
| `--pjx-toast-border` | `var(--border)` |
| `--pjx-toast-radius` | `var(--radius-md)` |
| `--pjx-toast-shadow` | `var(--shadow-md)` |
| `--pjx-toast-gap` | `0.5rem` |
| `--pjx-toast-z` | `1000` |
| `--pjx-toast-info` | `var(--brand, #5c8fa8)` |
| `--pjx-toast-success` | `#3e7d4f` |
| `--pjx-toast-warning` | `#b07415` |
| `--pjx-toast-error` | `#b3261e` |

### PJXAvatarStack tokens

| Token | Default |
| --- | --- |
| `--pjx-avatar-stack-overlap` | `-0.5rem` |
| `--pjx-avatar-stack-ring` | `var(--surface)` |

### PJXPageLoader tokens

| Token | Default |
| --- | --- |
| `--pjx-page-loader-backdrop` | `rgb(0 0 0 / 0.15)` |
| `--pjx-page-loader-z` | `9999` |
| `--pjx-page-loader-size` | `2rem` |

### PJXChipInput tokens

| Token | Default |
| --- | --- |
| `--pjx-chip-input-gap` | `0.375rem` |
| `--pjx-chip-input-chip-bg` | `var(--surface-alt)` |
| `--pjx-chip-input-chip-fg` | `var(--text)` |
| `--pjx-chip-input-chip-radius` | `var(--radius-full)` |
| `--pjx-chip-input-border` | `var(--border)` |
| `--pjx-chip-input-focus` | `var(--border-focus, var(--border))` |
| `--pjx-chip-input-radius` | `var(--radius-md)` |
| `--pjx-chip-input-padding` | `0.375rem 0.5rem` |

### PJXFormField tokens

| Token | Default |
| --- | --- |
| `--pjx-form-field-gap` | `0.375rem` |
| `--pjx-form-field-label-size` | `0.875em` |
| `--pjx-form-field-label-color` | `var(--text)` |
| `--pjx-form-field-help-color` | `var(--text-muted)` |
| `--pjx-form-field-error` | `#b3261e` |

### PJXToggleSwitch tokens

| Token | Default |
| --- | --- |
| `--pjx-toggle-switch-width` | `2.75rem` |
| `--pjx-toggle-switch-height` | `1.5rem` |
| `--pjx-toggle-switch-track` | `var(--border)` |
| `--pjx-toggle-switch-track-on` | `var(--brand)` |
| `--pjx-toggle-switch-thumb` | `#fff` |
| `--pjx-toggle-switch-radius` | `var(--radius-full)` |
| `--pjx-toggle-switch-gap` | `0.5rem` |

### PJXSegmentedControl tokens

| Token | Default |
| --- | --- |
| `--pjx-segmented-control-bg` | `var(--surface-alt)` |
| `--pjx-segmented-control-border` | `var(--border)` |
| `--pjx-segmented-control-radius` | `var(--radius-full)` |
| `--pjx-segmented-control-gap` | `0.25rem` |
| `--pjx-segmented-control-padding` | `0.25rem` |
| `--pjx-segmented-control-active-bg` | `var(--surface)` |
| `--pjx-segmented-control-active-fg` | `var(--text)` |
| `--pjx-segmented-control-active-shadow` | `0 1px 3px rgb(0 0 0 / 0.12)` |
| `--pjx-segmented-control-fg` | `var(--text-muted)` |
| `--pjx-segmented-control-focus` | `var(--border-focus, var(--brand))` |

### PJXPasswordInput tokens

| Token | Default |
| --- | --- |
| `--pjx-password-input-border` | `var(--border)` |
| `--pjx-password-input-radius` | `var(--radius-md)` |
| `--pjx-password-input-focus` | `var(--border-focus, var(--brand))` |
| `--pjx-password-input-toggle-color` | `var(--text-muted)` |
| `--pjx-password-input-eye-size` | `1.25rem` |
