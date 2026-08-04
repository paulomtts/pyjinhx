# Migration guide

!!! warning "Older sections describe older versions"
    Sections are newest-first, and each one describes the APIs as they were **at that
    release**. Anything below the current section may name symbols that have since been
    removed and patterns that no longer work — read them for the upgrade steps between
    those two versions, never as a description of how pyjinhx behaves today. The topmost
    section is the only one that describes current behaviour.

## 1.1.x → 1.2.0

1.2.0 moves response composition out of the render path and into one framework-free
module, `pyjinhx.responses`. The visible consequence is that `ReactiveResponse` is gone:
a handler returns a component, a string, `None`, or its own framework's response object,
and `compose()` turns that into the body and htmx headers. See
[Responses](api/responses.md) for the full surface.

### `ReactiveResponse` is deleted (breaking)

The class, its module, and its export are removed — `from pyjinhx import ReactiveResponse`
and `from pyjinhx.reactive import ReactiveResponse` both raise `ImportError`. There is no
shim. Every construction rewrites to a plain return value:

| BEFORE (1.1.x) | AFTER (1.2.0) |
|---|---|
| `return ReactiveResponse(primary=c.render(), mounted=request)` | `return c` |
| `return ReactiveResponse(primary=html, mounted=request)` | `return html` |
| `return ReactiveResponse(mounted=request)` | `return None` |
| `return ReactiveResponse(primary="")` | `return None` |
| `return ReactiveResponse(redirect="/todos")` | `return RedirectResponse("/todos", status_code=303)` |
| `return ReactiveResponse(redirect="/todos", redirect_mode="location")` | `return Response(status_code=204, headers={"HX-Location": "/todos"})` |
| `mounted=request`, `assets=request` | drop them — `PjxScopeMiddleware` parses both headers onto the session |

```python
# BEFORE (1.1.x)
from pyjinhx import ReactiveResponse


@app.post("/todos")
def add_todo(request: Request, text: str = Form(...)):
    todo = store.add(text)
    row = ItemRow(todo_id=todo.id, id=f"row-{todo.id}")
    return ReactiveResponse(primary=row.render(), mounted=request)


# AFTER (1.2.0)
@app.post("/todos")
def add_todo(text: str = Form(...)):
    todo = store.add(text)
    return ItemRow(todo_id=todo.id, id=f"row-{todo.id}")
```

Returning `None` is how you say "this request has no primary fragment". The composer emits
the fan-out on its own, plus `HX-Reswap: none` so htmx leaves the triggering element alone.

### Fan-out belongs to the composer, not to `render()` (behavioral)

`pyjinhx.responses.compose(result, *, session=None)` is what walks the client's manifest,
evicts the request's dirtied keys, and appends the OOB legs. `render()` returns one
component's markup and nothing else — it never appended OOB swaps, and code written on the
assumption that it did was relying on `ReactiveResponse` to do the work.

Fan-out is now **unconditional**: it runs on every path that produces a body, because the
dirtied keys belong to the request rather than to whatever shape the handler chose to
return. It does not require a registered backend; the backend only parses `X-PJX-Mounted`
and `X-PJX-Assets` onto the session and turns the composed result into its own response
type.

`compose()` recognises exactly four shapes:

- a `BaseComponent` — rendered as the primary,
- `None` — an empty primary, plus `HX-Reswap: none`,
- a `str`, `Markup`, or any object with `__html__` — used verbatim as the primary,
- anything else — returned as the `PASSTHROUGH` sentinel, untouched.

**Migration:** where a handler returned `Cls(...).render()` "so dependents ride along",
return the component itself. The string form still fans out (it is the third shape above),
but the component form is what lets pyjinhx exclude the primary's own regions from the
walk correctly and keeps the response typed.

### Redirects are native, with no pyjinhx surface (behavioral)

There is no pyjinhx `redirect()` helper and no setting to enable this. Return your
framework's own redirect. When the response carries a 3xx status **and** a `Location`
header, and the request carried `HX-Request`, it is translated to `204` +
`HX-Redirect` — which is what htmx can actually follow. A non-htmx request gets the real
3xx untouched, so the same handler still works from a plain browser navigation.

Detection is duck-typed on shape rather than on `RedirectResponse`, so hand-built and
third-party redirect responses translate too.

```python
from fastapi.responses import RedirectResponse


@app.post("/logout")
def logout():
    session.clear()
    return RedirectResponse("/login", status_code=303)
```

`HX-Location` (htmx's client-side ajax navigation, the old `redirect_mode="location"`) has
no pyjinhx surface at all — spell it yourself and it passes through untouched:

```python
from fastapi import Response

return Response(status_code=204, headers={"HX-Location": "/login"})
```

### Reactive roots stamp four attributes (behavioral)

A reactive root is stamped with `data-pjx-id`, `data-pjx-type`, `data-pjx-hash`, and —
only when the class has a `PjxKey` field — `data-pjx-load`. `data-pjx-type` is the
**snake_case tag name**, not the class name.

`data-pjx-reacts` is *not* stamped by the framework. `pjx.js` only reads it, to scope its
loading-indicator behavior, so a component that wants that behavior has to render the
attribute itself:

```html
<li data-pjx-reacts="todos" class="row">{{ title }}</li>
```

### A `LookupError` out of `load()` is the only "region is gone" signal (behavioral)

This is the change most likely to be silently wrong in an existing app.

A miss in the request-scoped instance registry does **not** mean a region is gone —
regions outside the primary tree miss it as a matter of course. The one thing that proves
a region no longer exists server-side is `load()` raising `LookupError`, and that is what
produces the delete swap:

```html
<div hx-swap-oob="delete:[data-pjx-id='row-7']"></div>
```

Raising is therefore part of `load()`'s contract. A `load()` that catches its store's
`KeyError` and returns a field-default instance gets its region swapped with a **blank
render** instead of deleted — no error, no warning, just an empty row left on the page.

```python
# BEFORE — swallows the signal; the client keeps a blank row forever
@classmethod
def load(cls, todo_id: int, ctx: TodoAppContext | None = None) -> "ItemRow":
    try:
        todo = ctx.store.get(todo_id)
    except KeyError:
        return cls(todo_id=todo_id)
    return cls(todo_id=todo_id, title=todo.text, done=todo.done)


# AFTER — let it raise; the region is deleted client-side
@classmethod
def load(cls, todo_id: int, ctx: TodoAppContext | None = None) -> "ItemRow":
    todo = ctx.store.get(todo_id)  # KeyError is the signal
    return cls(todo_id=todo_id, title=todo.text, done=todo.done)
```

`KeyError` and `IndexError` both subclass `LookupError`, so an ordinary dict or list lookup
against your own store is already the correct signal — the migration is usually deleting a
`try`/`except`, not adding a `raise`.

### Load keys arrive as their declared type (behavioral)

`data-pjx-load` round-trips through an HTML attribute as a string, but the framework
validates it back to the `PjxKey` field's **declared** type before calling `load()`. A key
declared `int` arrives as an `int`.

**Migration:** delete any hand-rolled coercion, and narrow the signature back to the type
you actually declared.

```python
# BEFORE (1.1.x) — widened signature plus manual coercion
@classmethod
def load(cls, todo_id: int | str, ctx: TodoAppContext | None = None) -> "ItemRow":
    todo_id = int(todo_id)
    ...


# AFTER (1.2.0)
@classmethod
def load(cls, todo_id: int, ctx: TodoAppContext | None = None) -> "ItemRow":
    ...
```

A value that will not validate is passed through untouched rather than raised on — `load()`
is entitled to reject it with its own error, and the walk turns that into a delete swap.

---

## 0.36.x → 1.0 (pyjinhx v2)

pyjinhx 1.0 is a rebuild, not an increment. The component model, template syntax, props,
slots, reactivity, and every builtin are the same as 0.36 — a v0.x app ports without a
redesign. What changed is a short list of behaviors that the rebuild deliberately did not
carry over, each one below with what to do instead.

### SFC `{# python #}` blocks removed (breaking)

Single-file components — a `{# python #}` block at the top of a template declaring the
component class inline — do not exist in v2 and are not deferred (ADR 0008). There is no
compatibility shim and no flag to re-enable them.

**Migration:** split the block into a normal Python class next to the template. Discovery
pairs them by name, so nothing else changes.

```html
<!-- BEFORE (0.36): card.html -->
{# python
class Card(BaseComponent):
    title: str
#}
<div class="card"><h2>{{ title }}</h2></div>
```

```python
# AFTER (1.0): card.py
from pyjinhx import BaseComponent


class Card(BaseComponent):
    title: str
```

```html
<!-- AFTER (1.0): card.pjx -->
<div class="card"><h2>{{ title }}</h2></div>
```

### Public `Parser` / `Tag` API removed (breaking)

The HTML parse-tree API (`Parser`, `Tag`, and the node-walking helpers around them) is not
public in v2 and has no compat shim (ADR 0011). v2 does not build a parse tree at all — it
composes a segment model, and exposes those types instead.

```python
# BEFORE (0.36)
from pyjinhx.parser import Parser

tags = Parser(html).parse()
for tag in tags:
    print(tag.name, tag.attrs)
```

```python
# AFTER (1.0) — no equivalent public API.
# If you were parsing rendered output to inspect it, parse it with an HTML library
# you control (e.g. html.parser, lxml, BeautifulSoup) instead of pyjinhx internals.
```

If you used `Parser`/`Tag` for something the segment model should cover, open an issue —
it is not a supported extension point today.

### Stray fields require the open subclass (breaking)

In 0.36, `BaseComponent` accepted extra fields — any attribute passed on a tag that was not
a declared prop landed on the instance. In v2, `BaseComponent` is strict: undeclared fields
raise a validation error. Accepting extras is opt-in via the open subclass (ADR 0006), which
is what classless `component()` and `{#def#}` prop headers are built on, so those keep
working unchanged.

```python
# BEFORE (0.36) — extras silently accepted on any component
class Card(BaseComponent):
    title: str


Card(title="Hi", subtitle="stray")  # subtitle absorbed
```

```python
# AFTER (1.0) — declare it, or subclass the open base
class Card(BaseComponent):
    title: str
    subtitle: str | None = None  # declare what you actually pass
```

Undeclared tag attributes are still passed through to the rendered root element — that is
unchanged. Only *fields on a strict component* are affected.

### Component slots are opaque (breaking)

A slot holding a component is an opaque node in v2 (ADR 0003). You can test it for
truthiness and render it, and `{{ field.props.x }}` / `{{ field }}` still work — but string
filters applied to it now raise a clear error instead of silently operating on rendered
markup. Slots holding **strings** are unchanged and still render raw HTML.

```html
<!-- BEFORE (0.36): string filters happened to work on a component slot -->
{% if header|trim %}<div class="hd">{{ header|upper }}</div>{% endif %}
```

```html
<!-- AFTER (1.0): truthiness + render, or reach into props -->
{% if header %}<div class="hd">{{ header }}</div>{% endif %}
{{ header.props.title }}
```

### Single-root violations now raise (breaking)

The single-root invariant is not new (it arrived in 0.18), but 0.36 still had a fallback
path that silently stamped attributes somewhere reasonable when a template had zero or
multiple top-level elements. v2 has no fallback: a template that is not exactly one root
element raises at render time, always.

```html
<!-- BEFORE (0.36): sometimes tolerated, attributes landed on the first element -->
<h2>{{ title }}</h2>
<p>{{ body }}</p>
```

```html
<!-- AFTER (1.0): one root, required -->
<section>
    <h2>{{ title }}</h2>
    <p>{{ body }}</p>
</section>
```

### Templates are `.pjx` + snake_case only (breaking)

Template autodiscovery in v2 probes exactly one filename per component: the snake_case form
of the class name with a `.pjx` extension (ADR 0007). The 0.36 probe list — `.html` and
`.jinja` extensions, and kebab-case filenames — is gone.

```text
BEFORE (0.36): any of these resolved for class UserCard
  user_card.html   user-card.html   user_card.jinja   user-card.jinja   user_card.pjx

AFTER (1.0): exactly one
  user_card.pjx
```

**Migration:** rename your component templates. An explicit `template=` path on the class
still overrides discovery, unchanged.

### Registry cross-reference in templates removed (breaking)

Templates can no longer reach a *peer* component instance through the registry — the
template-visible cross-reference lookup is gone with no replacement (ADR 0004, ADR 0009).
The instance registry still exists, but it is reactivity-only now: it maps name+id to an
instance and its cached render so OOB fan-out and not-dirtied cache hits work. It is not a
template-visible lookup table.

**Migration:** pass what you need. If component B rendered a value out of component A, make
that value a prop on B (or read it from shared state in `load()` on a `ReactiveComponent`),
rather than reaching across the tree at render time. There is no flag to restore the old
behavior — this is the change most likely to require a small refactor, and it is the reason
render cycles are now bounded by the nesting/`load()` chain alone.

### OOB nesting dedup is structural now (no action needed)

When a reactive update dirties both a parent and a child, only the outermost swap is sent.
That behavior is unchanged. What changed is how it is computed: 0.36 used a heuristic over
rendered markup, while v2 reads containment straight off the segment tree, which knows the
nesting structure exactly. Anywhere the heuristic and the structure disagreed, the structure
is right — so the only expected difference is fewer redundant swaps, never a missing one.
Nothing to change in your code.

### Cross-request `InvalidationBackend` is not in 1.0 yet (deferred)

> **Deferred, not removed.** The cross-request invalidation backends (Redis, SQLite) are
> not part of the 1.0 release and are planned for a post-1.0 version (ADR 0011).

The **per-request** load cache ships in 1.0 and is unchanged — single-process apps see no
difference. If you configured a Redis or SQLite backend to share invalidation across
processes, that configuration has no 1.0 equivalent yet; stay on 0.36 until it lands if you
depend on it.

### Still removed from earlier versions

`PJXPanel` and `PJXLazyPanel` were removed before v2 and stay removed — v2 does not
resurrect them. Use `PJXTabPanel` / `PJXLazyLoad` as in later 0.x releases. Every other
builtin ports to 1.0.

### Internals with no migration

Two mechanism changes are visible in the source but not in your app: root attributes are
stamped by splicing at a recorded offset instead of reparsing the document (same override
semantics), and the render cycle guard is simpler now that cross-reference resolution is
gone. No action needed for either.

Finally, `pjx-ls` (the language server) is out of scope for 1.0 and has not been updated for
v2 yet.

---


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
    title: str = ""  # escaped
    body: Slot = ""  # raw HTML


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

!!! danger "Never true, and superseded — do not copy this pattern"
    `.render()` does not append OOB swaps and never did; this section documents an
    intent the implementation never matched. Since 1.2.0, fan-out is attached by
    [`compose()`](api/responses.md) to whatever a handler **returns**, and
    `ReactiveResponse` no longer exists. See the [1.1.x → 1.2.0](#11x-120) section at the top of this page.

Any component's `.render()` now appends out-of-band swaps for dirtied mounted
reactive regions when a client backend is active and mutations occurred — not
only `ReactiveComponent.render()`. A command-result view returned from a mutating
route now updates mounted read-models with no wrapper:

```python
@app.post("/generate")
def generate():
    report = controller.generate()  # @mutates dirties "reports", "quota"
    return ReportSummary(report=report).render()  # non-reactive; counters fan out OOB
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
class Bad(ReactiveComponent, react={"todos"}):  # bare string
    ...


# TypeError: Bad: react only accepts MutationKey members; got 'todos'


# Raises at decoration time:
@mutates("todos")  # bare string
def save(): ...


# TypeError: @mutates only accepts MutationKey members; got 'todos'
```

Fix: define a `MutationKey` subclass and use its members everywhere.

### Inheritance

A subclass without `react=` inherits the parent's keys through the MRO. Re-declaring `react=` on a subclass **replaces** the parent's set (no union).

---

## Migrating from pre-1.0 (v0.x) to 1.0 (pyjinhx v2)

> **Audience:** humans and AI coding agents on any v0.x release (0.4 through 0.36) moving
> to 1.0. Everything above this section (0.36.x → 1.0, and the version-by-version notes
> from 0.8 through 0.36) also applies — read those for the mechanical, template-level
> breaks. This section covers the deeper break: v2 is a rebuild of the render/reactive
> engine itself, so the *entry points* you call from Python changed shape even though the
> component model (Pydantic fields, adjacent templates, slots, `react=`, `@mutates`)
> carried over.

### `Renderer` / `Registry` are gone

v0.x centered on a `Renderer` object (`Renderer.get_default_renderer()`,
`Renderer.set_default_environment()`, instance `.render()` returning `Markup`) plus a
`Registry` with a `request_scope()` middleware for per-request isolation. Neither class
exists in 1.0 — `pyjinhx/__init__.py` exports no `Renderer` and no `Registry`. In their
place:

- **Rendering** is a free function: `pyjinhx.render(component, session=None)` returns a
  finished HTML string. There is no renderer instance to configure or default.
- **Request scoping** comes from `pyjinhx.RenderSession` plus the request-scope machinery
  `setup()` installs on your app — you no longer hand-roll a `Registry.request_scope()`
  middleware.
- **Environment/template wiring** happens through `setup()`'s `components_root=` (and, for
  a custom Jinja `Environment`, by constructing `RenderSession` yourself) instead of
  `Renderer.set_default_environment()`.

```python
# BEFORE (v0.x)
from pyjinhx import Renderer

Renderer.set_default_environment(Path(__file__).parent)
renderer = Renderer.get_default_renderer()
html = renderer.render(MyComponent(...))

# AFTER (1.0)
from pyjinhx import render, setup

setup(app, components_root=Path(__file__).parent)
html = render(MyComponent(...))
```

### `pyjinhx.parser` / `pyjinhx.tags` are gone

The public HTML/PascalCase-tag parser (`Parser`, `Tag`, wherever your v0.x release had it
— `pyjinhx.parser` or the later `pyjinhx.tags`) is not part of 1.0's public surface (ADR
0011, see above). v2 does not build a parse tree at all; it composes a segment model
internally and exposes no equivalent public type. If you were parsing rendered output to
inspect it, parse it with an HTML library you control (`html.parser`, `lxml`,
BeautifulSoup) instead of pyjinhx internals.

### `pyjinhx.builtins` today

`pyjinhx.builtins` no longer ships the older component set (`Card`, `Tooltip`, `Panel`,
`PanelTrigger`, `Notification`, `Avatar`, `Modal`, …). The current builtins are the HTMX
data/nav family — `PJXTable` and its parts (`PJXTableHead`, `PJXTableBody`, `PJXTableRow`,
`PJXTableHeaderCell`, `PJXTableCell`), `PJXPaginator`, `PJXRegionLoader`, `PJXPageLoader`,
`PJXLazyLoad` — plus the `ui/` component set. Check `pyjinhx.builtins.__init__` for the
current list rather than assuming a name from an older release survived.

### `PjxContext` is narrower

v0.x's `PjxContext` supported user-data injection and `load()`-parameter introspection. 1.0's
`PjxContext` is a deliberately narrower, read-only facade over session and reactive
state — no user-data injection, no mutation methods. To reach per-request app data inside
`load()`, subclass `pyjinhx.AppContext` and pass an instance via `setup()`'s
`context_factory=`:

```python
from typing import Self

from pyjinhx import AppContext, ReactiveComponent, setup


class MyAppContext(AppContext):
    def __init__(self, db, user):
        self.db = db
        self.user = user


setup(app, context_factory=lambda request: MyAppContext(get_db(request), request.user))


class TodoList(ReactiveComponent):
    @classmethod
    def load(cls, ctx: MyAppContext | None = None) -> Self:
        return cls(items=ctx.db.todos_for(ctx.user) if ctx else [])
```

### `pyjinhx.render` → `pyjinhx.rendering`

The render-pipeline submodule is `pyjinhx.rendering` in 1.0 (`render()`, `render_level()`
internals). If you imported from a `pyjinhx.render` submodule directly rather than the
top-level `pyjinhx.render` function, update the import path.

### What still works unchanged

- `BaseComponent` authoring: Pydantic fields + adjacent template, auto-registered.
- `react=`, `@mutates`, `MutationKey`, and OOB fan-out for `ReactiveComponent`.
- `RenderSession` as the per-request rendering handle (construction changed; the concept
  did not).

See [Reactivity](reactivity.md) for the full reactive model and
[Configuration](guide/configuration.md) for `setup()`, `PjxSettings`, and invalidation
backends.
