# Changelog

## 0.28.1 — Engine dedup & internals cleanup (2026-06-23)

### Changed
- Internal refactor removing three confirmed code duplications in the core engine
  (no behavior change):
  - A single root-tag attribute splice now handles both `data-pjx-*` and the
    OOB `hx-swap-oob` stamp — the duplicate `utils.stamp_root_attributes`
    (and its helpers) was removed, leaving `root_attrs.apply_root_attrs` as the
    sole splicer.
  - The redis and sqlite invalidation backends now share a `_decode_keys`
    payload parser and a `DEFAULT_CHANNEL` constant on `InvalidationBackend`.
  - The redundant render-cycle guard in `BaseComponent._wrap_component_value`
    was removed; `_render`'s own guard already covers every nested render.
- The invalidation channel constant is now `InvalidationBackend.DEFAULT_CHANNEL`
  (the module-level `pyjinhx.integrations.redis`/`sqlite` `DEFAULT_CHANNEL`
  constants were removed).

### Docs
- Added a mermaid sequence diagram of the reactive request → primary + OOB-swap
  round-trip to the Reactivity guide.

## 0.28.0 — HTMX data & navigation builtins (2026-06-23)

### Changed
- **Breaking:** removed `PJXPanel`/`PJXPanelTrigger`. The panel pattern is now a
  `PJXTab` used outside a `PJXTabList` — a standalone trigger (button semantics,
  `aria-current` active state) that drives a `PJXTabGroup`'s panels from anywhere
  on the page. One engine now powers both tabs and panels.

  **Migration — before:**
  ```python
  PJXPanel(id="workspace", panels={"files": "<p>Uploaded assets.</p>", "chat": "<p>Team conversations.</p>"})
  PJXPanelTrigger(panel_id="workspace", panel="files", content="Files")
  PJXPanelTrigger(panel_id="workspace", panel="chat", content="Chat")
  ```
  **After:**
  ```python
  PJXTab(id="trig-files", panel="workspace-files", selected=True, content="Files")
  PJXTab(id="trig-chat", panel="workspace-chat", content="Chat")

  PJXTabGroup(id="workspace", content=(
      PJXTabPanel(id="workspace-files", content="<p>Uploaded assets.</p>").render()
      + PJXTabPanel(id="workspace-chat", content="<p>Team conversations.</p>").render()
  ))
  ```
  Standalone trigger content must be inert (plain text or `<span>`) — the `PJXTab` wrapper is itself the interactive control.
- **Breaking:** renamed `PJXLazyPanel` → `PJXLazyLoad` and added a `tag` field
  (`"div"` / `"li"` / `"tr"`). It's no longer just a panel — it's deferred content
  that loads on a trigger (viewport reveal / region reveal / load) and swaps itself
  in. With `tag="li"`/`"tr"` it works as an **infinite-scroll sentinel** at the end
  of a `<ul>`/`<tbody>`: on reveal it `outerHTML`-replaces itself with the next batch
  plus a fresh `PJXLazyLoad`. Migration: `PJXLazyPanel(...)` → `PJXLazyLoad(...)` (same
  fields). Ships no JS.

### Added
- **Table builtins:** `PJXTable` + `PJXTableHead` / `PJXTableBody` / `PJXTableRow` /
  `PJXTableHeaderCell` / `PJXTableCell` — thin semantic wrappers over a real
  `<table>` with style tokens (`striped`, `sticky_header`, `density`, `bordered`),
  a `caption`, an opt-in sortable header (focusable button + `aria-sort`, you wire
  `hx-get`), and selectable rows (leading checkbox cell for plain-form submission).
  htmx-aware by passthrough; ships no client JS. New "pure passthrough" wiring guide
  in the htmx integration docs.
- **`PJXPaginator`:** a generated, htmx-aware pagination control — windowed page
  links (`first/prev · 1 … 4 5 6 … 20 · next/last`) driven by `page`/`total_pages`/`url`
  (a `{page}` template). Each link is a real `<a href>` and gains `hx-get`/`hx-target`/`hx-swap`
  (+`hx-push-url`) only when a `target` is set, so it degrades to plain navigation. Ships no JS.
  Pairs with `PJXTable`.

### Fixed
- **`PJXButton` loading state:** the embedded region loader no longer renders an oversized
  spinner that overflows the button — the spinner is now sized to the button (the veil still
  masks the label).
- **`PJXDropdown` trigger:** the trigger button is now themed (surface/border, like the menu)
  instead of rendering as an unstyled browser button.
- **`PJXDrawer`:** the open dialog now clips its sliding box (`overflow: hidden`), so the page
  no longer shows a transient horizontal scrollbar during the open/close animation.

## 0.27.1 — tab group width + CSS fixes (2026-06-22)

### Fixed

- **`PJXTabGroup` no longer jumps around / leaves stale space.** The group now fills its container
  (`width: 100%`) instead of shrink-wrapping to content, so it stays put when a tab is closed or a
  different panel is shown. The tab CSS was also consolidated — the dead dict-era `.pjx-tab-group__tab`
  rules were removed and the duplicate `.pjx-tab-group__list`/`__panel` rules (one of which left the
  panel body without horizontal padding) now live in a single file each, giving the panel body
  deterministic styling. (#135)

## 0.27.0 — resizable px/content floors + compound tabs (2026-06-22)

### Added

- **`PJXResizablePanel.min`/`max` accept pixel and content floors.** In addition to a percentage, a
  bound can be `"120px"` (pixels) or — for `min` — `"content"`, which floors the panel at its intrinsic
  min-content so a fixed child (e.g. a header strip) stays visible at any viewport size. Enforced via
  CSS (robust on resize) and honored exactly by drag/keyboard. (#148)

### Changed

- **`PJXTabGroup` becomes compound (breaking).** The `tabs={label: panel}` dict is replaced by
  composable parts — `PJXTabGroup` / `PJXTabList` / `PJXTab` / `PJXTabPanel` — enabling per-tab icons
  (`icon`), a close affordance (`closeable` → cancelable `pjx:tab:close` / `pjx:tab:closed`), pinned
  tabs (`pinned`), dynamic add/remove, and decoupled (inline or lazy) panels. Tabs and panels pair by
  explicit `id`/`panel`/`tab` or, when omitted, by order. Roving-tabindex keyboard (Arrows / Home /
  End / Enter / Delete) and the `pjx:reveal` lazy-panel integration are kept. Migration:
  `PJXTabGroup(tabs={"Home": home})` → `<PJXTabGroup><PJXTabList><PJXTab selected>Home</PJXTab></PJXTabList><PJXTabPanel>…</PJXTabPanel></PJXTabGroup>`. (#135)

## 0.26.0 — composable builtin parts + resizable split pane (2026-06-21)

### Changed

- **`PJXButton` collapses `start`/`center`/`end` into a single `{{ content }}` slot (breaking).**
  The prescriptive icon-text-icon layout via `start`/`center`/`end` slots is replaced by a single
  freeform `content` field — put an icon, text, or any markup there however you like.
  `variant`, `block`, `loading`, `disabled`, `type` are unchanged; the loading spinner still
  auto-appends after the content. Migration: replace `PJXButton(center="Save")` with
  `PJXButton(content="Save")`, and `PJXButton(start="<icon>", center="Add")` with
  `PJXButton(content="<icon> Add")` (or nest in tag form:
  `<PJXButton variant="primary"><PJXIcon name="plus"/> Add</PJXButton>`).
- **`PJXAccordion` is now composed of parts (breaking).** The slot-based monolith
  (`label`, `header`, `actions`) is replaced by three `{{ content }}`-composed builtins:
  `PJXAccordion` (the `<details>` shell), `PJXAccordionTrigger` (the `<summary>`, with the
  auto chevron), and `PJXAccordionContent` (the body). Actions are now an opt-in
  `<div class="pjx-accordion__actions">` placed inside the trigger. `PJXAccordionGroup` is
  unchanged. Migration: replace `<PJXAccordion label="T">body</PJXAccordion>` with
  `<PJXAccordion><PJXAccordionTrigger>T</PJXAccordionTrigger><PJXAccordionContent>body</PJXAccordionContent></PJXAccordion>`.
- **`PJXCard` is now composed of parts (breaking).** The slot-based monolith
  (`title`, `header`, `body`, `footer`) is replaced by four `{{ content }}`-composed builtins:
  `PJXCard` (the `<article>` shell), `PJXCardHeader` (with a `title` convenience that renders
  `<h3 class="pjx-card__title">`, falling back to its content), `PJXCardBody`, and
  `PJXCardFooter`. Migration: replace `<PJXCard title="T">body</PJXCard>` with
  `<PJXCard><PJXCardHeader title="T"/><PJXCardBody>body</PJXCardBody></PJXCard>`.
- **`PJXModal` is now composed of parts (breaking).** The slot-based monolith
  (`title`, `header`, `body`, `footer`, `close_label`, `close_content`) is replaced by four
  `{{ content }}`-composed builtins: `PJXModal` (the `<dialog>` shell), `PJXModalHeader` (with
  a `title` convenience and the auto-included close button), `PJXModalBody`, and
  `PJXModalFooter`. The dialog JS and behavior stay on the shell. Migration: replace
  `<PJXModal title="T">body</PJXModal>` with
  `<PJXModal><PJXModalHeader title="T"/><PJXModalBody>body</PJXModalBody></PJXModal>`.
- **`PJXDrawer` is now composed of parts (breaking).** The slot-based monolith
  (`title`, `body`, `footer`, `close_label`, `close_content`) is replaced by four
  `{{ content }}`-composed builtins: `PJXDrawer` (the `<dialog>` shell, keeping `side`),
  `PJXDrawerHeader` (with a `title` convenience and the auto-included close button),
  `PJXDrawerBody`, and `PJXDrawerFooter`. The dialog JS and behavior stay on the shell.
  Migration: replace `<PJXDrawer title="T">body</PJXDrawer>` with
  `<PJXDrawer><PJXDrawerHeader title="T"/><PJXDrawerBody>body</PJXDrawerBody></PJXDrawer>`.
- **`PJXEmptyState` collapses presentational slots into `content` (breaking).** The
  prescriptive slots (`image`, `title`, `description`, `action`, `actions`) are removed; a
  single freeform `content` field replaces them — compose whatever markup you need inside.
  `suggestions` (interactive chips) and `class_name` are unchanged. CSS tokens for the
  removed per-element rules (`--pjx-empty-state-title-size`, etc.) are also removed.
  Migration: replace `PJXEmptyState(title="No results", description="…", action="<button>…</button>")` with
  `PJXEmptyState(content="<h3>No results</h3><p>…</p><button>…</button>")`.
- **`PJXTooltip` is now composed of parts (breaking).** The two-slot monolith
  (`trigger`, `tip`) is replaced by three `{{ content }}`-composed builtins:
  `PJXTooltip` (the `<span>` shell, keeping `placement`), `PJXTooltipTrigger` (the
  focusable trigger, `tabindex="0"`), and `PJXTooltipContent` (`role="tooltip"` body).
  The tooltip JS finds parts by class within `.pjx-tooltip` and sets `aria-describedby`
  at runtime. Migration: replace `PJXTooltip(trigger="T", tip="Hint")` with
  `PJXTooltip(content=PJXTooltipTrigger(content="T").render() + PJXTooltipContent(content="Hint").render())`.

### Added

- **`PJXResizableGroup` / `PJXResizablePanel` / `PJXResizableHandle` — drag-to-resize split pane.**
  Compose panels separated by draggable handles inside a `row`/`column` group; dragging a handle
  trades space between its two neighbors (percentage sizing, responsive). Keyboard-resizable
  (Arrow / Home / End on the focusable `role="separator"` handle), `min`/`max` per panel, a
  `pjx:resize` event for app-side persistence, and nesting a perpendicular group for a resizable
  grid. (#134)

## 0.25.1 — stale `{#def#}` header warning + type-checker cleanup (2026-06-21)

### Added

- **Stale `{#def#}` header warning.** When a hand-written `BaseComponent` subclass is rendered
  and its template contains a `{#def#}` header, pyjinhx now emits a one-time `logger.warning`
  explaining that the header is ignored (the class's declared fields take precedence). The warning
  fires at most once per component name (module-level dedup set) and is silenced for classless
  components (`_pjx_classless = True`), so header-driven and factory components are unaffected.
  The check uses a cheap leading-regex on the template source file — no full header parse.

  Warning message:
  ```
  <Card>: a {#def#} header is present but a Python class is registered —
  the header is ignored. Remove the header (or the class).
  ```

### Changed

- **Type-checker clean across the package.** pyright/basedpyright (standard mode) now report zero
  errors for `pyjinhx`. The changes are behavior-preserving, and two improve the editor experience
  for library code: the class-form `ReactiveComponent.render()` / instance-form `render()` are now
  typed via a descriptor, and a keyed component's `load(cls, key)` no longer trips an
  incompatible-override error against the zero-arg abstract `load`.

## 0.25.0 — slot-escaping consistency (2026-06-19)

### Fixed

- **Builtin text fields no longer carry a misleading `str | BaseComponent` type.** Several
  builtin fields (`PJXButton.center`, `PJXModal`/`PJXDrawer`/`PJXCard`/`PJXEmptyState.title`,
  `PJXEmptyState.description`) were typed `str | BaseComponent` but rendered their string value
  **escaped** — so a passed component rendered raw while a markup string escaped, an inconsistency
  and a latent XSS footgun. These are now plain `str` (text, escaped by default), matching their
  actual behavior and the autoescape-by-default security posture. Icons/markup go in the adjacent
  `Slot` fields (`start`/`end`, `header`, `image`/`action`). A new convention test
  (`test_swept_fields_holding_components_are_slots`) enforces the invariant: any builtin field
  whose type can hold a `BaseComponent` must be a slot (children field or `Slot`-typed).

### Breaking

- `PJXButton.center`, `PJXModal.title`, `PJXDrawer.title`, `PJXCard.title`, `PJXEmptyState.title`,
  and `PJXEmptyState.description` no longer accept a `BaseComponent` value (they are now `str`).
  Pass rich/markup content through the components' slot fields instead.

### Docs

- Brought the `/pyjinhx` Claude Code skill (`docs/integrations/claude-code.md`) up to date: added an
  **Escaping & slots** section (autoescape-by-default, `Slot` opt-in, the "type matches escaping"
  convention), `Slot` in the public-API import block, `.pjx` in template auto-discovery, and
  corrected the builtins roster (37 components; added the missing `PJXAccordion`,
  `PJXAccordionGroup`, `PJXButton`, `PJXIcon`).

## 0.24.1 — classless content escape fix (2026-06-19)

### Fixed

- **Classless / undeclared `content` children no longer render HTML-escaped.** When a
  component received inner content but did not *declare* a `content` field (a classless
  `{#def … #}` component, or a subclass without `content`), `{{ content }}` was autoescaped,
  forcing `{{ content | safe }}`. `_build_template_context` only slot-wrapped *declared*
  fields; the children field arriving as a pydantic extra was missed. The extras loop now
  slot-wraps it too (via the existing `_is_slot_field` check), so inner content renders raw
  regardless of whether the receiving component declares `content`. (#125)

## 0.24.0 — .pjx template extension (2026-06-19)

### Added

- **`.pjx` template extension.** Templates can now use the `.pjx` extension alongside
  `.html` and `.jinja`. `.pjx` is tried first during auto-discovery, so a `widget.pjx`
  takes precedence over a co-located `widget.html`/`widget.jinja`. The extension list is
  centralized in `pyjinhx.utils.TEMPLATE_EXTENSIONS`.

## 0.23.2 — classless component assets (2026-06-19)

### Fixed

- **Classless / `{#def#}` / `component()` components now collect co-located CSS/JS.** Assets
  co-located with template-only components (built via the `{#def … #}` prop-header or via
  `component("Name")`) were never inlined because the asset guard only checked for the exact
  `BaseComponent` class name, missing the dynamically-named subclasses those paths produce.
  Added a `_pjx_classless` ClassVar marker set on all dynamically-built subclasses and broadened
  the guard to include it; the factory render path now also resolves the template path so
  `apply_component_render_assets` can locate the asset directory. (#122)

## 0.23.1 — security & slot fixes (2026-06-19)

### Fixed

- **Autoescape was defeated for components containing nested PascalCase tags.**
  HTML entities produced by autoescape were decoded during tag expansion (the
  `HTMLParser`-based tag parser decoded entities back into raw text), re-emitting
  escaped scalars as raw HTML and reopening the XSS hole for any component that
  embeds a nested tag (e.g. `PJXAccordion`, `PJXButton` loading state) — including
  user components that embed builtin tags. The tag parser now re-escapes emitted
  text, so entities survive the round-trip while slot HTML structure and
  attributes (passed through verbatim) are untouched. (#120)
- **Several builtin icon/element slots were escaping their string values.** The
  0.23.0 `Slot` migration missed `PJXButton.start`/`end`, `PJXDropdown.trigger`,
  `PJXTooltip.trigger`, and `PJXModal`/`PJXDrawer.close_content`, so a string
  value (e.g. an inline icon) HTML-escaped instead of rendering. Also fixed
  `PJXAccordion.header`/`actions`: their `Slot | None` annotation silently dropped
  the slot marker (`Optional[Annotated[...]]` loses the metadata) — the marker now
  sits on the outer `Annotated[str | BaseComponent | None, PjxSlot()]`. (#118)

## 0.23.0 — autoescape by default (2026-06-18)

### Added

- **Autoescape by default.** Template output is now HTML-escaped (Jinja runs with
  `autoescape=True`): scalar props, text, attribute values, and loop-derived
  values are escaped, closing the default XSS hole. (#113)
- **`Slot` type** (`from pyjinhx import Slot`) — declares a raw-HTML field
  (`str | BaseComponent`) whose string value renders unescaped. Works on scalar
  fields and on `Slot`-annotated `list`/`dict` collections (string elements
  render raw). A component's children/`content` field is always a slot; nested
  `BaseComponent` values render raw via `__html__`. (#113)

### Breaking

- **Scalar values are now HTML-escaped.** Strings that previously rendered raw
  (`<b>x</b>`) now escape to entities. Raw HTML in a scalar field requires an
  opt-in: declare the field as `Slot`, use `{{ value|safe }}` in the template, or
  pass a `BaseComponent` instance. Builtin slot fields are pre-typed `Slot` and are
  unaffected. See the [migration guide](docs/migration.md). (#113)

## 0.22.0 — issue batch: AccordionGroup, accordion actions, avatar/empty-state data, icons; swap-asset fix (2026-06-18)

### Added

- **`PJXAccordionGroup`** — a first-class builtin that treats a set of
  `PJXAccordion`s as one group, with `mode="exclusive" | "multi"` and a `gap`.
  Exclusive-open is coordinated by a small guarded-IIFE script. (#106)
- **`PJXAccordion` `actions` slot** — non-toggling action buttons (restore /
  delete, …) pinned to the end of the trigger. Clicks inside it `preventDefault()`
  the native `<summary>` toggle *without* `stopPropagation()`, so the buttons'
  own htmx/Alpine handlers still fire. (#103)
- **`PJXAvatar`** accepts an arbitrary pixel/CSS size (`size: str | int`); the
  named tokens (`sm`/`md`/`lg`) still emit the `pjx-avatar--{size}` class. (#77)
- **`PJXAvatarStack`** accepts structured `dict` items
  (`initials`/`color`/`alt`/`name`) and renders its own pills, alongside the
  existing string / component shapes. (#77)
- **`PJXEmptyState` suggestion chips** (`suggestions`) — a first-class
  "click a chip → dispatch an event" pattern (the event name is read from a
  `data-*` attribute, never interpolated into JS). (#77)
- Three icons added to the vendored Lucide subset — `building`,
  `triangle-alert`, `brain` (and a stale `alert-triangle` name corrected). (#99)

### Fixed

- **Swap-delivered head assets now reach the page.** The 0.19.0 mechanism
  emitted `hx-swap-oob="beforeend:head"` fragments, but htmx core silently drops
  OOB swaps targeting `<head>` — so reactive swap-ins needing assets absent at
  cold load rendered unstyled. `pjx.js` now applies those `data-pjx-asset`
  `<style>`/`<script>` elements to `<head>` itself. (#105)

## 0.21.1 — single root-attribute stamp pass (2026-06-18)

### Changed

- Internal: the renderer stamps reactive `data-pjx-*` and pass-through
  `extra_attrs` onto the root element in a single pass (previously two
  back-to-back locate-and-rebuild passes). Behavior-preserving; reactive root
  attribute order may differ.

## 0.21.0 — htmx ships with the runtime (2026-06-18)

### Added

- htmx (the reactive transport `pjx.js` depends on) is now vendored and inlined
  ahead of `pjx.js` on reactive root renders, so reactivity works without
  manually adding an htmx `<script>`. The inlined copy self-guards
  (`if (!window.htmx)`) and never double-loads when the page already has htmx.
- `setup(inject_htmx=False)` / `PJX_INJECT_HTMX=false` opts out for apps that
  manage their own htmx. `pjx.js` now logs a `console.error` when htmx is
  missing instead of failing silently. Regenerate the vendored copy with
  `scripts/vendor_htmx.py`.

## 0.20.0 — `{#def#}` prop headers for classless components (2026-06-18)

### Added

- A template-only component may declare its props in a leading
  `{#def title: str, count: int = 0 #}` header; pyjinhx parses it safely (via
  `ast`, no code execution) into a validated pydantic model — so classless
  components get defaults, required-checks, and type coercion without a Python
  class. Applied on both the `<Tag/>` path and the `component()` factory.

## 0.19.1 — gallery polish + Dropdown/Popover defaults (2026-06-18)

### Added

- Component gallery: multi-variation boxes (badge/button/icon/…), a
  first-variation-only code snippet, a fixed Skeleton rendering, and a
  Notification replay button.

### Fixed

- `PJXDropdown` menu items get sensible default styling (they were unstyled
  native buttons); `PJXPopover` panels get default content padding.

## 0.19.0 — structural builtins, INLINE swap assets, REFERENCE removed (2026-06-18)

### Added

- New structural builtins: **`PJXIcon`** (vendored Lucide set), **`PJXButton`**,
  **`PJXAccordion`**.
- Reactive OOB swaps deliver missing **INLINE** component assets (CSS/JS),
  deduped by a client-reported token (`X-PJX-Assets`). (See the 0.22.0 fix above
  for the `<head>`-delivery follow-up — #96, #105.)

### Removed (breaking)

- The `REFERENCE` asset mode and its URL-emission / resolver APIs
  (`set_asset_url_resolver`, `set_default_runtime_url`, …). `AssetMode` is now
  `{INLINE, NONE}`. For external/CSP/CDN delivery, render in `NONE` and serve a
  bundle built from `Finder.all_assets()`.

## 0.18.0 — single-root invariant + universal attribute pass-through (2026-06-17)

### Added

- Inline attributes on any PascalCase tag are injected onto the component's
  root element automatically (new `root_attrs` module), and every component is
  enforced to render exactly one root element.

### Changed

- `collect_extra_attrs` now returns a dict (replacing `render_extra_attrs`); the
  `extra_attrs_html` template token is dropped from builtins. `class_name`
  guidance scoped to builtins in the docs.

## 0.17.0 — ReactiveResponse accepts mutation keys (2026-06-17)

### Added

- `ReactiveResponse(*keys)` dirties the given mutation keys and fans out the
  OOB swaps in one call.

## 0.16.0 — ReactiveResponse class (2026-06-17)

### Changed (breaking)

- `reactive_response()` is replaced by the `ReactiveResponse` class.

## 0.15.0 — `component()` factory + setup wiring (2026-06-17)

### Added

- `component(name)` factory for html-only (classless) components.
- `dirty()` for imperative reactive-key dirtying.
- `setup()` wires the `components_root` Jinja environment and mounts
  `static_root`.

### Changed

- Removed `pyjinhx_lifespan`; `setup()` and backend wiring tidied.

## 0.14.0 — PjxContext method injection (2026-06-15)

### Added

- `PjxContext` is injected into component instance methods, classmethods, and
  staticmethods that declare it (threaded through bound args, so positional-only
  params work).

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
