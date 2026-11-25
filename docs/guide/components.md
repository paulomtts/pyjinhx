# Creating Components

Components are the building blocks of your UI. Each component is a Python class paired with a Jinja2 template.

## Basic Component

A component has two parts:

### 1. Python Class

```python
from pyjinhx import BaseComponent


class Card(BaseComponent):
    id: str  # Required - unique identifier
    title: str  # Required field
    subtitle: str = ""  # Optional with default
```

Extra CSS/JS assets are auto-discovered from adjacent `.css`/`.js` files sharing the component's snake_case stem — the same stem as its template, so `Card` picks up `card.css` and `card.js` — see [Asset Collection](assets.md) — not declared as fields on the class.

### 2. HTML Template

PyJinHX uses **Jinja2** templates for its components:

```html
<!-- card.pjx -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    {% if subtitle %}
        <p class="subtitle">{{ subtitle }}</p>
    {% endif %}
</div>
```

!!! tip "You can use PascalCase components inside templates"
    You can even use PascalCase components as custom tags **inside your component templates**. This lets you compose components by nesting, like `<Button .../>` or `<UserCard>...</UserCard>`, directly within other templates. PyJinHx will automatically discover and render them as components.


## The `id` Field

`id` is **auto-generated** (`pjx-<n>`) when omitted. Pass an explicit id for stable hooks (CSS selectors, htmx targets, reactive OOB targeting):

```python
button = Button(id="submit", text="Submit")  # explicit — stable hook
button = Button(text="Submit")  # auto-generated pjx-<n>
```

!!! tip "Using your own id scheme"
    Override `id` with a `default_factory` to apply your own generation strategy — for example a UUID:

    ```python
    import uuid
    from pyjinhx import BaseComponent
    from pydantic import Field


    class MyComponent(BaseComponent):
        id: str = Field(default_factory=lambda: str(uuid.uuid4()))
        # ... other fields ...
    ```

    A subclass that redeclares `id: str` **without** a default makes it required at instantiation time.


!!! tip "Turning auto-ids off"
    Set the `auto_id` class var to `False` to make `id` mandatory for that component — the `pjx-<n>` fallback is disabled and omitting `id` fails validation, whether you instantiate it from Python or write `<Tag/>` in a template (see [PascalCase Tags](tags.md)).

!!! warning "Reactive components need an explicit `id`"
    `ReactiveComponent` declares no `id` of its own, so it inherits the same `pjx-<n>` fallback — and that value is **not** stable across renders. A reactive region has to stay addressable for out-of-band swaps to find it, so always pass an explicit, stable `id=` (e.g. `TodoCounter(id="todo-counter")`).


## Template Discovery

Templates are automatically discovered based on the class name, which is converted to
snake_case and given the `.pjx` extension. That is the only naming convention there is —
no `.html`/`.jinja` fallbacks, and no kebab-case:

| Class Name | Template File |
|------------|---------------|
| `Button` | `button.pjx` |
| `ActionButton` | `action_button.pjx` |
| `UserCard` | `user_card.pjx` |

!!! warning "Template Location Requirement"
    Templates must be in the same directory as the Python class file.

A subclass with no adjacent template inherits the nearest ancestor's template and class
assets, each resolved independently (first found per kind walking the MRO). Mixing a
framework base with a component base works the same way — `class LiveBadge(ReactiveComponent,
PJXBadge, react={...})` renders `pjx_badge.pjx`, the nearest template on the MRO.

## Single-root rule

Every component template must render exactly **one** top-level HTML element. Rendering a
template with zero or two or more sibling top-level elements raises a `ValueError`:

```html
<!-- WRONG: two siblings at the top level -->
<h2>{{ title }}</h2>
<p>{{ body }}</p>

<!-- RIGHT: wrap them in a single root -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    <p>{{ body }}</p>
</div>
```

Conditional roots are fine — the check runs on the rendered output, so any branch that
resolves to a single element passes:

```jinja
{% if href %}<a href="{{ href }}">{{ label }}</a>{% else %}<button>{{ label }}</button>{% endif %}
```

## Attribute pass-through

Every inline tag attribute becomes a constructor argument of the component class, so on a
declared component each attribute must be a **declared field**. There is no automatic
injection of stray attributes onto the root element: an attribute the class doesn't declare
is a `ValidationError`, not a pass-through.

```python
class Card(BaseComponent):
    id: str
    title: str  # declared field — fills the template context
    subtitle: str = ""  # declared field — fills the template context
```

```html
<!-- ValidationError: hx-get is not a Card field -->
<Card id="orders" title="Orders" hx-get="/orders"/>
```

To let a component carry arbitrary `hx-*` / `data-*` attributes, declare a field for them and
emit it on the root yourself — this is what the built-in UI components do with their
`extra_attrs` dict:

```python
from pydantic import Field


class Card(BaseComponent):
    id: str
    title: str
    extra_attrs: dict[str, str] = Field(default_factory=dict)
```

```jinja
<div id="{{ id }}"{% for name, value in extra_attrs.items() %} {{ name }}="{{ value }}"{% endfor %}>
    <h2>{{ title }}</h2>
</div>
```

```html
<Card id="orders" title="Orders" extra_attrs='{"hx-get": "/orders", "hx-trigger": "every 5s"}'/>
```

Template-only components (no Python class, or created with `component()`) are the loose case:
they accept undeclared attributes and expose them as template variables, so you decide where —
and whether — they land in the markup.

## Escaping and slots

Template output is **HTML-escaped by default**. pyjinhx runs Jinja with
`autoescape=True`, so the special characters `& < > " '` in a value are turned
into entities (`&amp; &lt; &gt; &#34; &#39;`) before they reach the page. This is
the safe default: a scalar prop, text, an attribute value, or a value derived in
a `{% for %}` loop is escaped, so user-supplied data can't inject markup or break
out of an attribute.

```python
PJXCardHeader(id="c", title="<script>alert(1)</script>")
# title renders as &lt;script&gt;alert(1)&lt;/script&gt; — not executable
```

**What renders as raw HTML (not escaped):**

- A component's **children**/`content` field (the `_pjx_children_field`, e.g.
  `PJXCardBody.content`) — its string value is emitted verbatim.
- Any field declared `Slot` (`from pyjinhx import Slot`). A `Slot` field is
  `str | BaseComponent`; its string value renders raw. `Slot` collections work
  too — string elements inside a `Slot`-annotated `list`/`dict` (e.g.
  `PJXDropdown.items`) render raw.
- Any **`BaseComponent`** value — a nested component always renders its own HTML
  raw via the `__html__` protocol, whether passed directly or inside a list/dict.

```python
# content is the children field → raw HTML
PJXCardBody(id="c", content="<p data-x='1'>hi</p>")
# renders <p data-x='1'>hi</p> verbatim
```

**Escape hatches** — when you trust the markup and want it raw in a *scalar*
field, choose one:

- Declare the field as `Slot` (`field: Slot = ""`).
- Mark it safe in the template: `{{ value|safe }}`.
- Pass a `BaseComponent` instance — it renders raw via `__html__`.

> Raw HTML is only as safe as its source. Reserve slots / `|safe` / nested
> components for markup you control; never pass unsanitized user input raw.

Prop-header props (`{#def ... #}`, below) follow the same rule: a header-declared
prop is **escaped** unless you mark it safe in the template (`{{ prop|safe }}`) or
the prop is the component's children field or is typed `Slot` (see
[Header reference](#header-reference)).

## One model, three shapes

A component is a pjx document, optionally owned by a Python class. A document is
markup plus up to three Jinja-comment blocks: `{#def ... #}` (props), `{#css ... #}`
and `{#js ... #}`. It lives either in a `.pjx` file or in the `template` string of
the class that owns it, and means the same thing in both places. The tag, the props
and the rendered output never depend on which you pick, and one project can mix all
three.

**T: template only.** One `.pjx` file, no Python.

    {#def id: str, label: str, count: int = 0 #}
    <span id="{{ id }}" class="badge">{{ label }} ({{ count }})</span>
    {#css
    .badge { border-radius: 999px; }
    #}

**C: class in one file.** One `.py` file; the class holds its document in `template`.

```python
from pyjinhx import ReactiveComponent

from app.todos import Keys, store


class Counter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=store.remaining())

    template = r"""
    <div class="counter">{{ remaining }} left</div>
    {#css
    .counter { font-weight: 600; }
    #}
    """
```

**S: split.** A `.py` class plus its `.pjx`, optionally with sibling `.css` and `.js`
(everything the earlier sections describe).

| If the component... | Shape |
|---|---|
| is props and markup, nothing computed in Python | T |
| needs Python: `load()`, a factory, a validator, a property, reactive keys, a subclass | C |
| needs Python and has a template long enough that you want full template tooling on it | S |
| has big assets, assets shared by subclasses with their own templates, or served in `LINK` mode | any shape, with those assets as sibling files |

Start in T, move to C the day you need a method, and fall back to S when the string
gets uncomfortable.

### The `template` attribute

- It must be **one plain string literal** assigned in the class body. pyjinhx reads it
  back from the module's source, so an f-string, a concatenation or a name raises
  `ValueError`.
- Use a **raw string** (`r"""..."""`). In a plain string, `\n` becomes a real newline,
  which changes the markup and shifts every line number after it. A template that
  contains `"""` can use `'''` instead.
- Line N of the template is line N of the `.py` file, so Jinja errors and tracebacks
  point straight into your module.
- An inline `template` beats an adjacent `.pjx` of the same class. It is inherited like
  a template file: a subclass with no template of its own renders its parent's.
- If a class has a pydantic field named `template`, that field keeps its usual meaning
  and is not treated as the inline template.
- Edits to the string are picked up on the next render without re-importing the module.
  But it is an edit to a `.py` file, so a dev server that restarts on `*.py` changes
  (uvicorn `--reload`, for instance) restarts for it, where a `.pjx` edit would not.
- Markup in a Python string has no highlighting or template diagnostics in most editors.

### Header reference

| Written | Becomes |
|---|---|
| `str`, `int`, `float`, `bool`, `list`, `dict`, `Any` | the builtin (`Any`: no coercion) |
| `Literal["a", "b"]` | `typing.Literal` (members must be literals) |
| `list[str]`, `dict[str, int]` | the real generic, arguments resolved recursively |
| `str \| int`, `T \| None`, `Optional[T]` | the real union |
| `Slot`, `Children` | pyjinhx's slot and children types |
| `ExtraAttrs`, `AttrValue` | pyjinhx's validated attribute types |
| `pkg.mod.Type` | that type, imported |

- An annotation outside this list falls back to `Any` and logs a warning. `list[Slot]`
  is a list of components, not a slot.
- A default is a literal, a dotted constant (`size: int = app.ui.PAGE_SIZE`), or a
  dotted name called with no arguments (`at: datetime.datetime = datetime.datetime.now()`),
  which is a factory run per instance. Mutable literals such as `[]` are safe.
- A dotted name is an import path, resolved with `pkgutil.resolve_name` when the
  component class is built, not at startup. Nothing from the template is compiled or
  executed. A bad path raises `ValueError` naming the template, the prop and the path.
- A bare name that is not in the table is never imported, so a typo cannot become an
  import. There are no relative paths.
- `id: str`, required and with no default, turns `auto_id` off for that component.
  Any other declaration of `id` is an error.
- The header may sit anywhere in the document, once. A second one raises
  `TemplateSyntaxError`.

### Folding existing components

`scripts/fold_components.py` in the pyjinhx repository does the mechanical moves. It is
a repo script, not public API. Every subcommand is a dry run that prints a diff and a
summary; add `--write` to apply it. Only files under the paths you pass are touched.

    uv run python scripts/fold_components.py assets app/components
    uv run python scripts/fold_components.py template app/components --write
    uv run python scripts/fold_components.py declass app/components --root app

| Command | Move | Refuses when |
|---|---|---|
| `assets` | sibling `.css`/`.js` into a `{#css#}`/`{#js#}` block of the template beside it | the text contains `#}`; a subclass with its own template inherits the asset; the template already has that block; the class's `template` is not a triple-quoted literal that can hold it |
| `template` | a class's adjacent `.pjx` into `template = r"""..."""` (S to C) | the class already assigns `template`; the text holds both triple-quote styles or ends in a backslash; indentation would change when read back |
| `declass` | a fields-only class into a `{#def#}` header, deleting the `.py` (S to T) | the class has methods, decorators, other bases or other statements; a type or default is not expressible in a header; the module holds more than the class and imports |

`declass` prints every remaining reference to a folded class name, because it reports
rather than rewrites imports (`--root` says where to look). The script exits 1 if it
refused anything, after processing the rest, and running it again finds nothing left to
fold. Run your tests after each subcommand.

## HTML-only components

A component doesn't always need a Python class. If you have a template with no
behaviour or typed fields — just markup — you can reference it from Python with
the `component()` factory instead of hand-writing a `BaseComponent` subclass:

```python
from pyjinhx import component

Card = component("Card")  # finds card.pjx under the default environment
Card(title="Hi", content="body").render()
```

`component(name, template_dir=None)` returns a registered `BaseComponent` subclass
bound to the discovered template (`card.pjx` for `"Card"`). By default it resolves the
template the same way tag rendering does — under the directory `setup(components_root=...)`
last registered — but you can pass `template_dir` explicitly to point at a different
directory instead. The result is a first-class component: instantiate it, pass it as a field
of another component, or use `<Card/>` in a template — they all resolve to the same class.
It's idempotent and never shadows a component you've actually declared. See
[`component()`](../api/base-component.md#component).

## Prop headers for classless components

A template-only component declares its props in a `{#def ... #}` header. pyjinhx
parses it into a validated pydantic model, so a classless component gets defaults,
required-checks, and type coercion without a Python class:

    {#def title: str, count: int = 0, variant: str = "primary" #}
    <article class="pjx-card pjx-card--{{ variant }}">
      <h3>{{ title }}</h3>
      <span class="badge">{{ count }}</span>
      <div>{{ content }}</div>
    </article>

- The signature is Python-style: `name`, `name: type`, `name = default`, or
  `name: type = default`. A prop with no default is **required**.
- Declared props are validated (`<Card/>` with a missing required prop, or a
  value that can't coerce, raises a clear error). **Undeclared** attributes are
  still accepted rather than rejected (`hx-*`, `data-*`, `@click`, `class`) and
  reach the template context — nothing places them in the markup for you.
- The header is a normal Jinja comment, so it never appears in the output.
- A hand-written Python class always takes precedence over a header; the header
  is then ignored and pyjinhx logs a warning.

The full vocabulary is in the [Header reference](#header-reference).

### Tags need no `component()` call

A template whose header is present answers its own `<Tag/>`. Discovery notes the
`.pjx` files no class claimed; the first time a tag has no class, pyjinhx reads
that file, and if it carries a `{#def#}` header (an empty `{#def #}` counts) it
builds the component and registers it. A file with no header stays plain markup.

If two such files share a tag (same stem in different directories) and one has a
header, the tag is ambiguous and raises `LookupError` naming the paths. Rename
all but one, or call `component("Name")` to pick the first. A class you declare
always wins over a template.

`component()` still works, and still reads the header when the class is built, so it
needs the template to be resolvable at call time: pass `template_dir`, or run
`setup(components_root=...)` first.

## Inline styles and scripts

A component can keep its CSS and JS inside its `.pjx` template instead of in sibling
`.css`/`.js` files, so one template (plus its class, if it has one) is the whole component:

    {#def title: str #}
    <article class="card">
      <h3>{{ title }}</h3>
    </article>

    {#css
    .card { padding: 1rem; border-radius: 8px; }
    #}

    {#js
    document.querySelectorAll(".card").forEach((el) => el.dataset.ready = "1");
    #}

- Each block is a single Jinja comment, `{#css ... #}` or `{#js ... #}`. The keyword
  must touch `{#` (`{#css`, not `{# css`), so a prose comment such as
  `{# css tweaks #}` stays a plain comment. Like the `{#def#}` header, a block never
  appears in the rendered output, and the template still renders in plain Jinja.
- A block can sit anywhere in the document, in any order relative to the `{#def#}`
  header. It is read statically: putting it inside `{% if %}` does not make it conditional.
- The body is taken verbatim, Jinja syntax included — `{{ }}` and `{% %}` are not
  evaluated. Like any Jinja comment, it ends at the first `#}`, so the body cannot
  contain that sequence.
- A template holds at most one block of each kind. A second one raises
  `jinja2.TemplateSyntaxError` naming the file and the second block's line when the
  component class is built. An empty block counts as no block.
- Block contents go through the same pipeline as sibling files (see
  [Asset Collection](assets.md)): shipped once per render session however many
  instances render, in the same path order, with the same `data-pjx-asset` token on
  inline styles, and in the swap-in delta for a region appearing for the first time.
- A sibling file and a block of the same kind are **both** shipped, sibling first, so
  block rules win a specificity tie against the file's.
- Blocks come from the template the class renders. A subclass with no template of its
  own renders its parent's, so it ships the parent's blocks; a subclass with its own
  template ships only that template's blocks (sibling files are still inherited up the
  class chain as before).
- `AssetMode.LINK` has no file to point a URL at, so a component with a block raises
  `ValueError` in LINK mode. Use `INLINE`, or `NONE` with a bundle: `all_assets()`
  lists each block as a path such as `ui/card.pjx#css`, and `read_text()`/`read_bytes()`
  on it return the block body, so the [one-bundle](assets.md#one-bundle-deployment)
  recipe works unchanged.

## Extra Fields

`BaseComponent` is **strict**: like a plain Pydantic `BaseModel`, it rejects unknown keyword
arguments with a `ValidationError`. Every prop a component accepts from Python has to be a
declared field.

```python
from pyjinhx import BaseComponent


class Example(BaseComponent):
    foo: int


Example(foo=1, bar=2)  # ValidationError: Extra inputs are not permitted
```

Classless components are the exception. A component built from a template — by
`component()` or by a `{#def #}` header — is generated with `extra="allow"`, so it
accepts undeclared keys and makes them available in the template context. That is what
lets `hx-*`, `data-*` and other stray attributes pass through to the root element (see
[Attribute pass-through](#attribute-pass-through)).

A hand-written class can opt into the same thing with pydantic's own config — there is no
pyjinhx-specific base to import:

```python
from pydantic import ConfigDict
from pyjinhx import BaseComponent


class Card(BaseComponent):
    model_config = ConfigDict(extra="allow")
    title: str = ""
```