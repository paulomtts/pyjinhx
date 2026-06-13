# Migration guide

## 0.11 → 0.12 (breaking: `PJX` prefix on all builtins)

Every builtin component is renamed with a `PJX` prefix, in Python and in tag form:

```python
# BEFORE (0.11)
from pyjinhx.builtins import Avatar, Modal
html = renderer.render('<Modal id="m" title="Hi"/>')

# AFTER (0.12)
from pyjinhx.builtins import PJXAvatar, PJXModal
html = renderer.render('<PJXModal id="m" title="Hi"/>')
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
`AssetMode` (`INLINE`, `REFERENCE`, `NONE`) per asset kind.

```python
from pyjinhx import AssetMode, Renderer

# OLD: inline_css=False meant "emit <link> tags instead of inlining CSS"
renderer = Renderer.get_default_renderer(inline_css=False)

# NEW: choose a CSS mode explicitly
renderer = Renderer.get_default_renderer(css_mode=AssetMode.REFERENCE)  # <link>/<script src>
# or AssetMode.NONE to skip emitting CSS entirely
# (the old default, inline_css=True, is AssetMode.INLINE)
```

Process-wide defaults moved to dedicated setters:

```python
Renderer.set_default_css_mode(AssetMode.REFERENCE)
Renderer.set_default_js_mode(AssetMode.INLINE)
Renderer.set_default_runtime_url("/static/pjx.js")   # used by REFERENCE mode
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
                                           →  Renderer.get_default_renderer(css_mode=AssetMode.REFERENCE)
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
- `pyjinhx.builtins` components — though as of 0.12 they carry a `PJX` prefix (`PJXCard`, `PJXTooltip`, `PJXPanel`, …).
- Child components as rendered strings, `id`-based addressing, and manual `hx-swap-oob`
  strings — still valid if you are not ready to adopt `ReactiveComponent` for a given region.

You can migrate the mechanical fixes today and adopt reactivity region-by-region later;
the two layers coexist.
