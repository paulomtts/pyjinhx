# Changelog

## 0.13.0 — OOB swaps ride along any render (2026-06-13)

### Added

- Any component's `.render()` now appends out-of-band swaps for dirtied mounted
  reactive regions when a client backend is active and mutations occurred — not
  only `ReactiveComponent.render()`. A route that mutates state and returns a
  non-reactive command-result view now updates mounted read-models with no
  wrapper. Fan-out happens once per request scope and never double-swaps a
  region already present in the response body.
- `pyjinhx.reactive.reactive_response(html)` — escape hatch attaching the same
  fan-out to responses that render no component (raw strings, `204`).

### Breaking changes (0.12.x → 0.13.0)

- `setup()` keyword `load_context_factory` is renamed `context_factory`. The
  old name is silently ignored (absorbed by `**kwargs`), so update call sites.

## 0.12.0 — PJX prefix on all builtins (2026-06-12)

### Breaking changes (0.11.x → 0.12.0)

- All builtin components are renamed with a `PJX` prefix, in Python and in
  tag form: `Avatar` → `PJXAvatar`, `<Modal/>` → `<PJXModal/>`, etc. The old
  names are gone (no aliases); they are now free for application components.
- Builtin CSS classes and auto-generated component ids use the `pjx-` prefix
  (was `px-`): `px-modal__inner` → `pjx-modal__inner`, auto ids `px-1` →
  `pjx-1`.
- The builtin browser API namespace is `window.pjx` (was `window.px`):
  `px.modal.open(...)` → `pjx.modal.open(...)`; DOM events `px:*` → `pjx:*`
  (e.g. `px:toast` → `pjx:toast`, `px:reveal` → `pjx:reveal`).
- `pascal_case_to_snake_case` / `pascal_case_to_kebab_case` are acronym-aware:
  `HTMLBlock` now resolves to `html_block.html` (was `h_t_m_l_block.html`).
  Rename template files for components whose class names contain consecutive
  capitals.
- Single-capital tags (e.g. `<X/>`) are no longer parsed as components.

Migration: prefix builtin imports and tags with `PJX`, and update CSS
selectors, `window.px.*` calls, and `px:*` event listeners to `pjx`. See
docs/migration.md for the full cheat sheet.

## 0.11.0 — nori migration fixes (2026-06-12)

Fixes for every finding from the nori 0.5.2 → 0.10.1 migration (#67, #68),
landed as PRs #69–#75.

### Breaking changes (0.10.x → 0.11.0)

- Registering two different component classes under the same name from
  different source files now raises `TypeError` instead of silently
  overwriting based on import order (#74). Same-file re-registration
  (autodiscovery, reload) is still allowed. To intentionally shadow a
  builtin: `class Avatar(BaseComponent, pjx_replace=True)`.
- Stray PascalCase tag attributes on **builtin** components now render onto
  the component's root element instead of being silently dropped
  (`<PopoverTrigger title="hello" hx-post="/x"/>` works) (#75). User
  components keep extras-as-template-context semantics.

### Fixed

- Parser no longer logs a `WARNING` for every plain HTML closing tag on
  well-formed input; the warning now fires only for genuinely interleaved
  closes around an open component tag (#68, #69).
- Render explosion fixed: registry peers injected into render contexts are
  consumed lazily (rendered only when a template actually references them),
  instead of eagerly re-rendered in every component's context. A page with 5
  registered siblings went from 32,784 renders to 2 (#72).
- The pjx.js client runtime is injected once per `Registry.request_scope()`,
  not once per top-level `render()` call — multi-root page assembly no longer
  duplicates the runtime (#70).
- Modules using `from __future__ import annotations` (PEP 563) can declare
  `Annotated[..., PjxKey()]` fields — string annotations are now resolved
  during class definition (#71).
- `<Modal>children</Modal>` maps children into `body` instead of silently
  discarding them; same for `Drawer`, `Card`, and `Alert` (#75).
- A keyed `load()` that explicitly pins an id equal to the kebab-cased class
  default keeps it; only defaulted ids get the `-{key}` suffix (#73).

### Changed

- `extra_attrs` values may contain `"` — they're emitted single-quoted
  (htmx `hx-headers`/`hx-vals` JSON now expressible); values containing both
  quote types are rejected (#75).
- Modal and Drawer close-button glyph is configurable via `close_content`
  (defaults to `✕`) (#75).
- Builtin CSS token defaults moved from `:root` to zero-specificity
  `:where(:root)`, so app-level `:root` overrides win regardless of bundle
  order (#73).

### Docs

- Retroactive note: `render()` now really returns `markupsafe.Markup` at
  runtime, matching its long-standing annotation (older versions, 0.5.2
  included, unescaped to a plain `str` before returning despite the `-> Markup`
  annotation). This silently changed concatenation: `pane.render() + raw_html_str`
  HTML-escapes the right-hand string, per markupsafe semantics. If you
  concatenate rendered output with raw HTML strings, use
  `str(pane.render()) + raw` or `pane.render() + Markup(raw)`.

## 0.10.1 — Render-cycle guard + Tooltip tag children (2026-06-11)

### Fixed

- Registered components that cross-reference each other inside
  `Registry.request_scope()` no longer recurse infinitely (#64). A render-stack
  guard on the session (keyed by type + id) renders cyclic references empty and
  logs a `render cycle suppressed` warning; sequential reuse and same-id
  components of different types are unaffected.
- `<Tooltip>text</Tooltip>` maps children to `tip` again (the v2 tag parser
  hardcoded `content`, which Tooltip lacks — text was silently dropped). Tag
  children now target a per-class field (`BaseComponent._pjx_children_field`).
- Supplying both children and the children-target attribute on one tag raises a
  clear `ValueError`; the attribute-only form (`<Notification content="hi"/>`),
  which previously raised a spurious `TypeError`, now works.

## 0.10.0 — Component aliasing via subclassing (2026-06-11)

A component subclass now resolves to its nearest ancestor's template and assets
through the MRO, so builtins can be subclassed into reactive components with no
templates of their own: `class LiveBadge(ReactiveComponent, Badge, react={Keys.TASKS})`.

### Added

- MRO-aware template/asset resolution: template, CSS, and JS each resolve
  independently to the nearest ancestor that ships the file — ship only
  `live-badge.css` and you replace the CSS while keeping the base template and JS.
- Safety guard: a class may have at most one concrete component base;
  `class X(Badge, Card)` raises at class definition. Framework bases
  (`ReactiveComponent`) don't count toward the limit.
- `TemplateNotFound` now lists every candidate tried across the whole MRO.
- Docs: "Making builtins reactive" recipe in the reactivity guide.

## 0.9.0 — `react=` class keyword + gallery polish (2026-06-10)

### Breaking changes (0.8.0 → 0.9.0)

- `reacts_to: ClassVar[set[str]]` is removed. Declare state keys as a class
  keyword: `class Counter(ReactiveComponent, react={Keys.TODOS})`. The old
  declaration raises a `TypeError` pointing at the new syntax.
- Both `react=` and `@mutates` accept only `MutationKey` members; bare strings
  raise `TypeError` (decoration time for `@mutates`). See the
  [migration guide](https://paulomtts.github.io/pyjinhx/migration/) for the 0.8 → 0.9 section.

### Docs

- Component gallery demos are centered in their iframes, and every snippet shows
  `.render()` on the top-level component.

## 0.8.0 — Builtins v2 (2026-06-10)

Every builtin now follows one contract: optional auto-generated `id`, `class_name`,
`extra_attrs` (validated dict rendered on the root), all copy as props (aria-labels included),
headless IIFE JS under the single `window.px` namespace, cancelable `px:*:before-*` hook events,
and a documented DOM contract. New builtins: ConfirmDialog, PromptDialog, ToastHost,
AvatarStack, PageLoader (28 exported components).

### Added

- Five new form-control builtins (33 exported components total): `ChipInput`, `FormField`,
  `PasswordInput`, `SegmentedControl`, `ToggleSwitch`.

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
