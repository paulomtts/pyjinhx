# Migration guide

## 0.34.x → next (`depends_on()` removed)

### `ReactiveComponent.depends_on()` removed (breaking)

`depends_on()` is no longer a method you can override. Cache indexing for keyed
components (a static `react` key plus the per-instance derived key) is computed
internally now — nothing to do if you never overrode it, which is the case for every
built-in component and, per a full-repo search, every user of this library found before
this change shipped.

If you *did* override it on a **keyed** component (one with a `PjxKey` field), your
override was always redundant with the default and can simply be deleted:

```python
# BEFORE
class TodoRow(ReactiveComponent, react={Keys.TODOS}):
    todo_id: Annotated[str, PjxKey()]

    def depends_on(self) -> set[str]:
        return super().depends_on() | set()  # redundant — delete the whole method

# AFTER
class TodoRow(ReactiveComponent, react={Keys.TODOS}):
    todo_id: Annotated[str, PjxKey()]
    # no depends_on() override needed — the default already includes the derived key
```

If you overrode it on a **non-keyed** component to narrow cache indexing to a subset of
its declared `react` keys based on loaded state (e.g. an admin-only panel that only
cares about one of two declared keys for guest users), there is no replacement. The
`react=` superset still governs correctness (dirtying any of its keys still triggers a
reload check); you lose only the cache-indexing precision the override gave you. File an
issue if you need this back — none of this library's own components used it.

## 0.22.x → next (autoescape by default)

### Template output is escaped by default (breaking)

Rendered output is now **HTML-escaped by default** (Jinja runs with
`autoescape=True`). Previously the renderer emitted markup raw (it called
`Markup(...).unescape()` on the final output), so any string value passed through
verbatim. Now scalar props, text, attribute values, and loop-derived values are
escaped — `& < > " '` become entities — which closes the default XSS hole.

**What changed for you:**

- **Scalar props that contained HTML now escape.** A `title`, `label`, `alt`, etc.
  holding `<b>x</b>` now renders `&lt;b&gt;x&lt;/b&gt;`.
- **Raw HTML now requires an opt-in.** To emit raw markup in a *scalar* field, do
  one of: declare the field as `Slot` (`from pyjinhx import Slot`), use
  `{{ value|safe }}` in the template, or pass a `BaseComponent` instance (renders
  raw via `__html__`).
- **Children/`content` and `Slot` fields still render raw**, including `Slot`
  collections (string elements in a `Slot`-annotated `list`/`dict`). Nested
  `BaseComponent` values still render raw via `__html__`.
- **`Slot` is exported from `pyjinhx`** (`from pyjinhx import Slot`) for declaring
  raw-HTML fields on your own components.

```python
from pyjinhx import BaseComponent, Slot

class Card(BaseComponent):
    title: str = ""      # escaped
    body: Slot = ""      # raw HTML

Card(title="<b>x</b>", body="<p>ok</p>")
# title → &lt;b&gt;x&lt;/b&gt;   body → <p>ok</p>
```

The builtins were updated for you — their slot fields (card `body`, modal/drawer
`header`/`footer`, tab group `tabs`, dropdown `items`, empty-state `actions`, …)
are typed `Slot` and keep rendering raw. Only *your own* scalar fields that relied
on raw passthrough need the opt-in above. See
[Escaping & slots](guide/components.md#escaping-and-slots).

**`PJXAvatarStack` — string items are now escaped.** If you passed pre-rendered
HTML strings as `avatars` items, those strings are now escaped. Use structured
dicts (`{"initials": "AB", "color": "#f00", ...}`) for pill rendering, or pass
`BaseComponent` instances for raw markup.

---

## 0.18 → 0.19

### REFERENCE asset mode removed (breaking)

`AssetMode.REFERENCE` is gone. `AssetMode` is now a two-member enum: `INLINE` and `NONE`.

The following APIs are removed:

- `Renderer.set_asset_url_resolver()` — registered a callable to map asset paths to public URLs for REFERENCE rendering
- `Renderer.set_default_runtime_url()` — set the public URL for `pjx.js` emitted in REFERENCE mode
- `Renderer.set_default_asset_dedup()` — toggled per-render `X-PJX-Assets` dedup for REFERENCE renders
- `client_script(mode=..., src=...)` — `mode` and `src` parameters are removed; call `client_script()` with no arguments

**Migration:** If you used REFERENCE mode for external/CSP/CDN delivery, switch to `AssetMode.NONE` and serve a pre-built bundle:

```python
from pyjinhx import AssetMode, Renderer
from pyjinhx.finder import Finder

# Build once at startup
CSS_PATHS, JS_PATHS = Finder("./components").all_assets()
# ... concatenate and serve as /assets/bundle.css + /assets/bundle.js

Renderer.set_default_js_mode(AssetMode.NONE)
Renderer.set_default_css_mode(AssetMode.NONE)
```

Link the bundles in your layout `<head>`. Components will no longer emit inline or URL-referenced asset tags — the bundle covers everything.

See [One-bundle deployment](guide/assets.md#one-bundle-deployment) for a full FastAPI example.

The bundle helpers (`Finder.all_assets()`, `asset_manifest()`, `resolver_with_hash()`, `make_default_asset_url_resolver()`, `Finder.layout_asset_tags()`, `DEFAULT_RUNTIME_URL`) are **unchanged** and remain the production path for `AssetMode.NONE`.

---

## 0.17 → 0.18

### Universal attribute pass-through + single-root invariant

Inline tag attributes on a PascalCase component tag are now automatically injected onto that
component's root element for **every** component — builtins, `BaseComponent` subclasses, and
template-only `.html` components. No template boilerplate is needed.

**For authors of custom components:** nothing to do for pass-through. The only required change
is ensuring every component template renders exactly **one** top-level element. Templates with
zero or two or more top-level elements now raise a `ValueError` at render time.

```html
<!-- BEFORE (0.17): was silently accepted, pass-through silently dropped -->
<h2>{{ title }}</h2>
<p>{{ body }}</p>

<!-- AFTER (0.18): wrap in a single root — required -->
<div id="{{ id }}">
    <h2>{{ title }}</h2>
    <p>{{ body }}</p>
</div>
```

### `{{ extra_attrs_html }}` template token removed

The `{{ extra_attrs_html }}` Jinja variable is no longer injected into the template context.
If your custom builtin or app-component templates contain `{{ extra_attrs_html }}`, remove
the token — injection is now automatic and placing the token would produce a blank string.

```html
<!-- BEFORE (0.17): builtin-only manual token -->
<div id="{{ id }}" class="pjx-card" {{ extra_attrs_html }}>…</div>

<!-- AFTER (0.18): token removed; attributes inject automatically -->
<div id="{{ id }}" class="pjx-card">…</div>
```

The `extra_attrs` field on `BaseComponent` still works: pass a dict and it is injected onto
the root alongside any stray tag attributes.

---

## 0.12 → 0.13

### `setup()` keyword `load_context_factory` → `context_factory`

The `setup()` keyword `load_context_factory` is renamed `context_factory`:

```python
# BEFORE (0.12)
setup(app, load_context_factory=lambda: AppContext(db=...))

# AFTER (0.13)
setup(app, context_factory=lambda: AppContext(db=...))
```

The old name is **silently ignored** (absorbed by `**kwargs`) — no error is
raised, so your context factory simply stops being installed. Update every call
site.

### Non-reactive renders now fan out OOB swaps

Any component's `.render()` now appends out-of-band swaps for dirtied mounted
reactive regions when a client backend is active and mutations occurred — not
only `ReactiveComponent.render()`. A command-result view returned from a mutating
route now updates mounted read-models with no wrapper:

```python
@app.post("/generate")
def generate():
    report = controller.generate()      # @mutates dirties "reports", "quota"
    return ReportSummary(report=report).render()   # non-reactive; counters fan out OOB
```

Fan-out happens once per request scope and never double-swaps a region already
present in the response body. For a response that renders no component (a raw
string, a `204`), use `from pyjinhx.reactive import ReactiveResponse`. The old
function `reactive_response(html)` is now the class `ReactiveResponse`, and the
dummy `""` is no longer needed — `ReactiveResponse()` works.

`ReactiveResponse`'s `html` is now **keyword-only** — pass it as
`ReactiveResponse(html="<p>…</p>")`, not positionally. The positional slots now
take mutation keys, so you can dirty and fan out in one call:
`ReactiveResponse(Keys.TODOS)` (or `ReactiveResponse(Keys.TODOS, html="<p>…</p>")`).

## 0.11 → 0.12 (breaking: `PJX` prefix on all builtins)

Every builtin component is renamed with a `PJX` prefix, in Python and in tag form:

```python
# BEFORE (0.11)
from pyjinhx.builtins import Avatar, Modal
html = renderer.render('<Modal id="m"/>')

# AFTER (0.12)
from pyjinhx.builtins import PJXAvatar, PJXModal
html = renderer.render('<PJXModal id="m"/>')
```

Related renames, all mechanical:

- Builtin CSS classes: `px-*` → `pjx-*` (e.g. `px-modal__inner` → `pjx-modal__inner`). Update any custom CSS targeting builtin classes.
- The browser API namespace: `window.px` → `window.pjx` (`px.modal.open(...)` → `pjx.modal.open(...)`), and DOM events `px:*` → `pjx:*` (e.g. `px:toast` → `pjx:toast`).
- Auto-generated component ids: `px-<n>` → `pjx-<n>`.
- Template auto-discovery is now acronym-aware: `HTMLBlock` resolves to `html_block.html` (previously `h_t_m_l_block.html`). Rename template files for your own components whose class names contain consecutive capitals.
- Single-capital tags (e.g. `<X/>`) are no longer parsed as components.

Your own component names no longer risk colliding with builtins — `Avatar`, `Card`, `Modal`, etc. are free for application code.

## 0.8 → 0.9 (breaking: `react=` class keyword + strict `@mutates`)

### `reacts_to` → `react=` class keyword

The `reacts_to: ClassVar[set[str]]` attribute is removed. Declare state keys as a class keyword instead:

```python
# BEFORE (0.8)
from typing import ClassVar
from pyjinhx import ReactiveComponent, MutationKey

class Keys(MutationKey):
    TODOS = "todos"

class Counter(ReactiveComponent):
    remaining: int
    reacts_to: ClassVar[set[str]] = {Keys.TODOS}

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=db.remaining())

# AFTER (0.9)
from pyjinhx import ReactiveComponent, MutationKey

class Keys(MutationKey):
    TODOS = "todos"

class Counter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=db.remaining())
```

Using the old `reacts_to` attribute raises at class-definition time:

```
TypeError: Counter: reacts_to was replaced by the react class keyword:
class Counter(ReactiveComponent, react={...})
```

### Strict `MutationKey` for both `react=` and `@mutates`

Both `react=` and `@mutates` now **only accept `MutationKey` members**. Bare strings raise `TypeError`:

```python
# Raises at class-definition time:
class Bad(ReactiveComponent, react={"todos"}):   # bare string
    ...
# TypeError: Bad: react only accepts MutationKey members; got 'todos'

# Raises at decoration time:
@mutates("todos")   # bare string
def save(): ...
# TypeError: @mutates only accepts MutationKey members; got 'todos'
```

Fix: define a `MutationKey` subclass and use its members everywhere.

### Inheritance

A subclass without `react=` inherits the parent's keys through the MRO. Re-declaring `react=` on a subclass **replaces** the parent's set (no union).

---

## Migrating from 0.4.x to the latest

> **Audience:** humans and AI coding agents upgrading a codebase built against the
> old (`~0.4.2`) render-only pyjinhx to the current release. It tells you what still
> works untouched, the handful of things that must change, and how to adopt the new
> reactive layer that did not exist in 0.4.x.

### The one-paragraph mental model

pyjinhx `0.4.x` was a **render-only** library: you defined `BaseComponent` subclasses
(Pydantic models with an adjacent Jinja template) and called `.render()`. Reactivity —
re-rendering parts of a page when state changed — was something **you** wired by hand:
route handlers built `hx-swap-oob="..."` HTML strings (`render_*_oob()` functions) and
returned them. The current release **keeps all of that working** and adds an **opt-in
reactive layer** (`ReactiveComponent` + `@mutates` + `setup()`) that does the OOB fan-out
for you. So migration is two separable jobs:

1. **Mechanical fixes** — a small, fixed list of moved/renamed/changed APIs (below). Do
   these and your existing app runs on the latest release unchanged in behavior.
2. **Optional adoption** — replace hand-written OOB string-building with
   `ReactiveComponent` where you want declarative reactivity. Incremental; do it one
   region at a time.

### Does my existing code still work? (compatibility matrix)

| Area | Status | Action |
|------|--------|--------|
| `from pyjinhx import BaseComponent` + Pydantic fields + adjacent `*.html` | ✅ Unchanged | None |
| `component.render()` → `Markup`, and `{{ component }}` in templates | ✅ Unchanged | None |
| `_update_context_(self, context, field_name, field_value, *, renderer, session)` hook | ✅ Unchanged | None |
| `from pyjinhx.renderer import Renderer, RenderSession` | ✅ Still re-exported | None |
| `Registry`, `Registry.request_scope()` request isolation middleware | ✅ Unchanged | None |
| `from pyjinhx.builtins import Card, Tooltip, Panel, PanelTrigger, Notification` | ⚠️ **Renamed in 0.12** | Add the `PJX` prefix: `PJXCard`, `PJXTooltip`, … (see 0.11 → 0.12 above) |
| `from pyjinhx.parser import Parser` (and `Tag`) | ⚠️ **Moved** | Import from `pyjinhx.tags` |
| `Renderer.get_default_renderer(inline_css=...)` | ⚠️ **Changed** | Use `css_mode=AssetMode.…` |
| `Renderer.set_default_environment("some_package")` | ⚠️ **Behavior change** | Pass an explicit path/`Environment` |
| Reactivity (`react={...}`, `@mutates`, OOB fan-out, `setup()`) | 🆕 **New since 0.4.x** | Opt in (see below) |
| Pre-0.7 reactive names (`StateKey`, `PyJinhxSettings`, `LoadContext`, `PjxLoad`, `client_script`) | ⚠️ Renamed/removed | See cheat sheet — only if you used them |

### Step 1 — Mechanical fixes

These are the only changes required to keep a 0.4.x app running on the latest release.

#### 1a. `pyjinhx.parser` → `pyjinhx.tags`

The internal HTML/PascalCase-tag parser moved. `Parser` and `Tag` now live in
`pyjinhx.tags`; the class API (including the `handle_decl` hook that 0.4.x apps sometimes
monkey-patched to preserve `<!DOCTYPE>`) is unchanged.

```python
# OLD
from pyjinhx.parser import Parser

# NEW
from pyjinhx.tags import Parser, Tag
```

If you monkey-patched `Parser.handle_decl` for `<!DOCTYPE>` preservation, just re-point it
at `pyjinhx.tags.Parser` — the method still exists.

#### 1b. `inline_css=` → asset modes

`Renderer.get_default_renderer()` no longer takes `inline_css`. Assets are now governed by
`AssetMode` (`INLINE`, `NONE`) per asset kind.

```python
from pyjinhx import AssetMode, Renderer

# OLD: inline_css=False meant "emit <link> tags instead of inlining CSS"
renderer = Renderer.get_default_renderer(inline_css=False)

# NEW: choose a CSS mode explicitly
renderer = Renderer.get_default_renderer(css_mode=AssetMode.NONE)  # skip emitting CSS entirely
# or AssetMode.INLINE (the old default, inline_css=True)
```

Process-wide defaults moved to dedicated setters:

```python
Renderer.set_default_css_mode(AssetMode.NONE)
Renderer.set_default_js_mode(AssetMode.INLINE)
```

#### 1c. `set_default_environment` is now path-based for strings

`set_default_environment` accepts an `Environment`, a filesystem path, or `None`. A bare
**string is now treated as a filesystem path** (`FileSystemLoader(os.fspath(value))`), not a
Python package name. If you relied on package-name resolution, pass an explicit directory:

```python
from pathlib import Path
from pyjinhx import Renderer

# Safe across versions: hand it a concrete directory (or a prebuilt Environment)
Renderer.set_default_environment(Path(__file__).parent)
```

#### 1d. Pre-0.7 reactive renames (only if you touched them)

0.4.x predates reactivity, so most 0.4.x apps skip this. If your code passed through an
intermediate `0.5`–`0.7` reactive API, apply these renames:

| Old | New |
|-----|-----|
| `StateKey` | `MutationKey` |
| `PyJinhxSettings` | `PjxSettings` |
| `LoadContext` | `PjxContext` |
| `PjxLoad` | `PjxKey` |
| `client_script()` | no longer top-level — `from pyjinhx.client import client_script` |

Also note the **public surface was curated from ~45 down to ~11 symbols**. Advanced/internal
symbols are no longer top-level — import them from their submodule
(e.g. `from pyjinhx.cache import LoadCache`, `from pyjinhx.tags import Parser`). The 11
top-level exports are: `BaseComponent`, `ReactiveComponent`, `Renderer`, `setup`,
`Registry`, `mutates`, `MutationKey`, `PjxKey`, `PjxContext`, `PjxSettings`, `AssetMode`.

### Step 2 — Wire `setup()` (prerequisite for reactivity)

Reactivity needs the client runtime, request scoping, and (optionally) a cross-worker
invalidation backend. One call wires all of it into a FastAPI/Starlette app. This
*replaces* a hand-rolled `Registry.request_scope()` middleware — `setup()` installs request
scoping for you.

```python
from pathlib import Path
from fastapi import FastAPI
from pyjinhx import setup, PjxSettings, Renderer

Renderer.set_default_environment(Path(__file__).parent)   # template root

app = FastAPI()

setup(
    app,
    settings=PjxSettings.from_env(),   # REDIS_URL / PJX_INVALIDATION_DB / PJX_REACTIVE_DEV
    # Inject per-request data reachable inside reactive load():
    context_factory=lambda request: AppLoadContext(db=get_db(request)),
)
```

Cache scope is **derived from the settings**: with no invalidation backend you get
per-request caching (safe for any number of workers); configuring a `RedisInvalidationBackend`
(multi-host) or `SqliteInvalidationBackend` (single-host, zero-infra) switches to per-worker
process caching with cross-worker invalidation fan-out.

If you are not adopting reactivity yet, you can keep your existing
`Registry.request_scope()` middleware and skip `setup()` entirely — render-only usage is
unaffected.

### Step 3 — Replace manual OOB with `ReactiveComponent`

This is the heart of the upgrade. In 0.4.x you refreshed dependent regions by building OOB
HTML by hand in the route:

```python
# BEFORE (0.4.x): the route knows every dependent region and hand-builds its OOB swap
def render_member_count_oob(*, members_count: int, members_total: int) -> str:
    return (
        f'<span id="members-counter" hx-swap-oob="outerHTML:#members-counter">'
        f'{members_count} of {members_total}</span>'
        f'<span id="nav-members-badge" hx-swap-oob="outerHTML:#nav-members-badge">'
        f'{members_total}</span>'
    )

@app.post("/orgs/{slug}/members/{mid}/remove")
def remove_member(slug: str, mid: str):
    org.remove_member(slug, mid)
    # You must remember to refresh the counter AND the badge AND the subtitle…
    return render_member_row_removed(mid) + render_member_count_oob(
        members_count=org.active_count(slug), members_total=org.total(slug)
    )
```

In the current release, each region **declares what state it derives from** and **how to
rebuild itself**, and the framework computes and emits the OOB swaps:

```python
# AFTER (latest): declare dependencies once; OOB fan-out is automatic
from pyjinhx import ReactiveComponent, MutationKey, mutates

class Keys(MutationKey):
    MEMBERS = "members"

# 1. The store marks which state it dirties
@mutates(Keys.MEMBERS)
def remove_member(slug: str, mid: str) -> None:
    ...

# 2. Each region rebuilds itself from the current world and lists its triggers
class MembersCounter(ReactiveComponent, react={Keys.MEMBERS}):
    count: int = 0
    total: int = 0

    @classmethod
    def load(cls) -> "MembersCounter":
        return cls(count=org.active_count(), total=org.total())

class NavMembersBadge(ReactiveComponent, react={Keys.MEMBERS}):
    total: int = 0

    @classmethod
    def load(cls) -> "NavMembersBadge":
        return cls(total=org.total())

# 3. The route renders only the primary; dependents swap themselves
@app.post("/orgs/{slug}/members/{mid}/remove")
def remove_member_route(slug: str, mid: str):
    remove_member(slug, mid)          # @mutates records Keys.MEMBERS as dirtied
    return MembersCounter.render()    # framework reloads every mounted region whose
                                      # react keys ∩ {MEMBERS} ≠ ∅, hashes them, and
                                      # appends an hx-swap-oob fragment for each *changed* one
```

What you delete: the bespoke `render_*_oob()` string builders and the route's burden of
remembering every dependent. What you gain: a region added later that reacts to `MEMBERS`
updates automatically, with no route change, and unchanged regions are skipped via state
hashing.

**Migration recipe per region:**

1. Identify a piece of state and give it a `MutationKey` member.
2. Decorate the store function that changes it with `@mutates(Keys.THAT_KEY)`.
3. Turn the region's `render_*()` function into a `ReactiveComponent` with a
   `classmethod load()` that rebuilds it from the current world, and a
   `react={...}` class keyword listing the `MutationKey` members it depends on.
4. For a multi-instance region (a row keyed by id), mark the key field
   `Annotated[int, PjxKey()]` and give `load(cls, key)` that one parameter.
5. Render the primary with `Cls.render(...)`; delete the manual OOB plumbing.

See [Reactivity](reactivity.md) for the full model (state hashing, nested-region
deduplication, keyed instances) and [Configuration](guide/configuration.md) for `setup()`
and invalidation backends.

### Quick cheat sheet

```text
# Imports that move / change
from pyjinhx.parser import Parser          →  from pyjinhx.tags import Parser, Tag
Renderer.get_default_renderer(inline_css=False)
                                           →  Renderer.get_default_renderer(css_mode=AssetMode.NONE)
Renderer.set_default_environment("pkg")    →  Renderer.set_default_environment(Path(".../templates"))

# Pre-0.7 reactive renames (skip if you never used them)
StateKey         → MutationKey
PyJinhxSettings  → PjxSettings
LoadContext      → PjxContext
PjxLoad          → PjxKey
client_script()  → no longer top-level — from pyjinhx.client import client_script

# Advanced symbols are no longer top-level — import from submodules
from pyjinhx.cache import LoadCache, CacheScope
from pyjinhx.tags import Parser, Tag
```

### What deliberately did **not** change

To keep migration cheap, these 0.4.x idioms are untouched:

- `BaseComponent` authoring: Pydantic models + adjacent `name.html` template, auto-registered.
- `.render()` returning `Markup`, and `{{ component }}` rendering in templates.
- The `_update_context_(self, context, field_name, field_value, *, renderer, session)`
  context-injection hook and `RenderSession`.
- `Registry.request_scope()` for per-request component isolation.
- `pyjinhx.builtins` components — though as of 0.12 they carry a `PJX` prefix (`PJXCard`, `PJXTooltip`, `PJXTable`, …).
- Child components as rendered strings, `id`-based addressing, and manual `hx-swap-oob`
  strings — still valid if you are not ready to adopt `ReactiveComponent` for a given region.

You can migrate the mechanical fixes today and adopt reactivity region-by-region later;
the two layers coexist.
