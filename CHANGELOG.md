# Changelog

## 0.8.0 — Builtins v2

Every builtin now follows one contract: optional auto-generated `id`, `class_name`,
`extra_attrs` (validated dict rendered on the root), all copy as props (aria-labels included),
headless IIFE JS under the single `window.px` namespace, cancelable `px:*:before-*` hook events,
and a documented DOM contract. New builtins: ConfirmDialog, PromptDialog, ToastHost,
AvatarStack, PageLoader (28 exported components).

### Breaking changes (0.7.x → 0.8.0)

| 0.7.x | 0.8.0 |
|---|---|
| `openModal(id)` / `closeModal(id)` + `onclick` | `px.modal.open/close(id)`, or `data-px-open="<id>"` / `data-px-close` |
| `openPxDrawer` / `closePxDrawer` | `px.drawer.open/close(id)` + the same data attributes |
| `togglePxDropdown(id)` / `closePxDropdown(id)` | gone — Dropdown wires `data-px-toggle`; the shared popover JS owns the behavior |
| `Dropdown(menu="...")` | `Dropdown(items=[...], menu_label="...")` |
| `Popover(content=, card_content=, position=, backdrop=)` (hover card) | compound `Popover` + `PopoverTrigger` + `PopoverPanel` (click toggle) |
| `dismissPxAlert(id)` | `data-px-close` inside the alert; hooks `px:alert:before-dismiss`/`dismiss` |
| `showNotification(id)` / `hideNotification(id)` | auto-shows on mount (`autoshow=True`); `px.notification.show/hide(id)` |
| `showLoadingOverlay` / `hideLoadingOverlay` / `resetLoadingOverlay` | `px.loader.region.show/hide/reset(id)`; also works as an `hx-indicator` target |
| `LoadingOverlay` component | renamed `RegionLoader` (same behavior; also an `hx-indicator` target) |
| `LazyPanel(trigger=...)` incantations for panels | `LazyPanel(when="reveal")` (`px:reveal` on `[data-px-region]`, + cancelable `px:before-reveal`) |
| `BaseComponent.id` required; empty id raised | optional — omitted/falsy ids become `px-<n>` (reactive components need stable ids, defaulted to the kebab-cased class name; pass explicit ids for instance-keyed rows) |
| Hardcoded `aria-label="Close"`/`"Dismiss"`/`"Submenu"`/`"Tabs"`/`"Loading"` | label props with English defaults |
| Tag instance-reuse updates skipped validation | updates re-validate per-field through pydantic |

Unchanged on purpose: `Drawer.side` keeps `left|right|bottom`; Panel/PanelTrigger/Tooltip/Card
public APIs are unchanged.

### Framework

- Extra `js`/`css` assets (`BaseComponent.js/css`) now collect for nested components, not just
  the render root.
- Autodiscovery import failures and unregistered-sibling-class fallbacks warn instead of
  failing silently.
- `Finder.all_assets()` + a documented one-bundle deployment recipe.
- Golden-HTML snapshot harness for all builtins (`tests/golden/`).
