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

## One model, four shapes

A component is a pjx document, optionally owned by a Python class. A document is
markup plus up to four Jinja-comment blocks: `{#def ... #}` (props), `{#css ... #}`,
`{#js ... #}` and `{#python ... #}` (the class). It lives in a `.pjx` file, in the
`template` string of the class that owns it, and means the same thing in both places:
the tag, the props and the rendered output do not depend on where the document lives.
One project can mix all four shapes.

The shapes differ in one way. A component built from a `{#def#}` header (T) accepts
undeclared attributes and passes them through to its root element, like any
[classless component](#extra-fields); a hand-written class (P, C, S) is strict and
rejects them with a `ValidationError` unless it opts in with `extra="allow"`.

**T: template only.** One `.pjx` file, no Python.

    {#def id: str, label: str, count: int = 0 #}
    <span id="{{ id }}" class="badge">{{ label }} ({{ count }})</span>
    {#css
    .badge { border-radius: 999px; }
    #}

**P: class in the `.pjx`.** One `.pjx` file; a `{#python` block holds the class.

```jinja
{#python
from pyjinhx import ReactiveComponent

from app.todos import Keys, store


class Counter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=store.remaining())
#}
<div class="counter">{{ remaining }} left</div>
{#css
.counter { font-weight: 600; }
#}
```

**C: class in one `.py`.** One `.py` file; the class holds its document in `template`.

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
| needs Python, and your team edits `.pjx` files with pjx-ls | P |
| needs Python, and you want every Python tool to work with no setup | C |
| needs Python and has a template long enough that you want full template tooling on it | S |
| has big assets, assets shared by subclasses with their own templates, or served in `LINK` mode | any shape, with those assets as sibling files |

Start in T, move to P or C the day you need a method, and fall back to S when the
string or the block gets uncomfortable.

### Which one: P or C?

P and C are the same component written two ways; they differ in which half gets
second-class tooling. Rendered output, tag, props and assets are identical.

| | P (the `.pjx` holds the class) | C (the `.py` holds the template) |
|---|---|---|
| Markup, CSS and JS in the editor | native, once an editor extension (pjx-ls) owns the `.pjx` | a Python string; plain unless you install an injection grammar |
| Python in the editor | through that extension, forwarded to Pyright | native |
| Type-checking in CI | needs generated `.pyi` stubs | nothing to do |
| ruff, coverage | partial: see [Known limits](#known-limits-of-shape-p) | native |
| Import | through pyjinhx's import hook, installed by `import pyjinhx` | Python's own |
| Several components in one file | one document per file; extra classes allowed | yes |
| Edit to the template under a `*.py` reloader | no restart | restart |
| Edit to the Python | restart, with a warning | restart |

Rule of thumb: use P if your team edits with pjx-ls, and C if you want every Python
tool to work with no setup.

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
| `str`, `int`, `float`, `bool`, `list`, `dict`, `tuple`, `Any` | the builtin (`Any`: no coercion) |
| `Literal["a", "b"]` | `typing.Literal` (members must be literals) |
| `list[str]`, `dict[str, int]`, `tuple[str, int]`, `tuple[int, ...]` | the real generic, arguments resolved recursively |
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
  component class is built, not at startup. The header is never `eval`'d, but treat a
  template as trusted code like any module: a dotted name imports its module (running
  that module's top level), and a `pkg.f()` default calls `f` for every instance. A
  bad path raises `ValueError` naming the template, the prop and the path.
- A bare name that is not in the table is never imported, so a typo cannot become an
  import. There are no relative paths.
- `id: str`, required and with no default, turns `auto_id` off for that component.
  Any other declaration of `id` is an error.
- The header may sit anywhere in the document, once. A second one raises
  `TemplateSyntaxError`.

### Shape P: the class in the `.pjx`

`app/ui/card.pjx` holds `Card` in a `{#python` block, and `from app.ui.card import Card`
works from ordinary Python. The block is an ordinary Jinja comment, so plain Jinja
renders the document and drops it.

The rules for the block, in the order the scanner checks them:

1. **Opener.** A line that is exactly `{#python`, with nothing but spaces, tabs or a
   `\r` after it. The `{#` is in column 0 and the keyword touches it. An indented
   `{#python` is a plain comment, and so is a prose comment such as
   `{#python is nice #}`. Inside `{% raw %}...{% endraw %}` or a tag it is not an opener
   either. A spaced `{# python` is a plain comment too, as is `{# python helpers #}`.
2. **Body.** Every line after the opener, compiled as written: no dedent, no stripping.
   Module-level code starts in column 0, as in a `.py` file.
3. **Closer.** The first `#}` after the opener. It must be alone on its line, in column
   0 (trailing spaces and tabs are allowed); `-#}` is refused. Jinja ends a comment at
   the first `#}`, so a `#}` inside the Python (in a string, a comment or `f"{n:#}"`)
   ends the block early. pyjinhx reports it as a `SyntaxError` on that line; write the
   pair as `"#" "}"` or move the code out.
4. **At most one** block per document, anywhere in it. By convention it comes first.
5. **No `{#def#}` header** in the same document: the class declares the props.
6. **Some markup.** A document with a block and nothing else but blocks, comments and
   whitespace is refused.

Nothing is implicitly in scope: the block is a plain module and imports what it uses,
`BaseComponent` included.

**The markup belongs to the class whose snake_case name is the file's stem**, as for
every other shape: `todo_count.pjx` belongs to `TodoCount`. The block may hold anything
a module may hold: imports, constants, helpers, and more component classes. A subclass
with no template of its own, such as `class TaskNameField(NameField)` inside
`name_field.pjx`, inherits the document. A class that wants its own markup needs its own
file. A `.py` subclass of a `.pjx` class works too, and inherits the document as usual.

Line numbers are the file's own. The markup's line N is file line N, and the Python is
compiled with the `.pjx` path as its filename and padded so that code line N is file
line N and column N is column N. A `SyntaxError`, a traceback, a `breakpoint()` and a
Jinja error all name the real file and line.

Refused, each message naming the file and line:

| Situation | Raised | When |
|---|---|---|
| No component class is named for the stem | `ImportError` | import |
| Two classes snake to the stem (`HTTPCard` and `HttpCard`) | `ImportError` | import |
| The same file is imported under a second module name | `ImportError` | import |
| A malformed block: unclosed, second, closer not alone, text after the closer | `SyntaxError` | import or class creation |
| A class in the block assigns `template` | `TypeError` | class creation |
| A `{#def#}` header in the same document | `TypeError` | class creation |
| No markup | `TypeError` | class creation |
| A sibling `card.py` defines the class that owns the document | `TypeError` | class creation |
| A `card.py` or `card/` directory shadows `card.pjx` | `ImportError` | `setup()`, and `stubgen --check` |

The last two rows are the same mistake in two places. Python finds `card.py` first, so
the import hook is never asked for `card.pjx`; neither file wins, and pyjinhx refuses the
pair. `card.py` plus a `card.pjx` with no block is shape S and needs no care.

### Importing and the hook

`import pyjinhx` appends one finder to `sys.meta_path`. Python asks it only for a name
every other finder failed to find, so an import that resolves never reaches it. A name
that does not resolve costs one `stat` per search-path entry (about 1.5 µs each), and a
file read only where a `.pjx` of that name exists. It answers if that file has a block; the block runs as
the module body, and `module.__file__` is the `.pjx`. Relative imports, `sys.modules`,
`pickle` and `copy.deepcopy` behave as they do for a `.py` file. No bytecode is cached.

There is one line you must write: **pyjinhx has to be imported before the first `.pjx`
module is.** A block begins with `from pyjinhx import ...`, but the hook is needed to
find the block. Put `import pyjinhx` in the `__init__.py` of your application's root
package:

```python
# app/__init__.py
import pyjinhx  # noqa: F401  installs the .pjx import hook
```

That covers the app, pytest, `python -m`, a reload subprocess and unpickling in a worker,
since each imports the root package first. pyjinhx ships no `.pth` file; the hook is the
one explicit line.

`setup(components_root=...)` imports every `.pjx` under the root that has a block, so a
block's class is known at startup like a class in a `.py` file: reactive fan-out,
`all_assets()` and `dev.dependency_graph()` all see it, and a block's import error fails
`setup()` instead of a request. Two consequences:

- Call `setup()` after the names your blocks import exist.
- A block and a module that import each other from different threads, one of them through
  `component_for_tag`, can raise `_DeadlockError`. Keep that cycle out of the blocks'
  imports.

A document created while the server runs is imported the first time its tag is used.

### Hot reload

| Edit | Without a restart |
|---|---|
| Markup, `{#css#}`, `{#js#}` | picked up on the next render, as for every shape |
| The `{#python` block | **not** picked up: the process keeps the class it imported |

pyjinhx does not reload modules; re-running a block would make a second class with the
same name while every importer still held the first. So that a markup edit shows and a
Python edit does not do so silently, pyjinhx logs one warning on the `pyjinhx` logger when
it re-reads a document whose block differs from the one imported:

    app/ui/card.pjx: the {#python block changed; restart the process to load it

It is logged once per edit, and any difference in the block's text counts, a comment
included. Two ways to run a dev server:

- Watch `*.py` only (uvicorn's default). Template edits are instant; a block edit needs a
  manual restart, and the warning says so.
- `uvicorn --reload --reload-include '*.pjx'`. Every `.pjx` save restarts the server, as
  an edit to a shape C template does.

### Stubs and type checking

Type-checkers do not read `.pjx`. `python -m pyjinhx.stubgen app` writes `card.pyi` next
to every `card.pjx` that has a block, so `from app.ui.card import Card` type-checks. The
stub is the block's Python with each function body replaced by `...`, and every class,
`def` and field keeps its line number. The generator parses the block and never runs it.
It overwrites or deletes only files that carry its marker comment, refuses to overwrite a
hand-written `.pyi`, and removes a marked stub whose `.pjx` is gone. See
[the command reference](../reference/commands.md#python-m-pyjinhxstubgen).

Recommended setup:

```gitignore
# generated by `python -m pyjinhx.stubgen`; this ignores every .pyi under app/ui
app/ui/**/*.pyi
```

```toml
[tool.pyright]
# a stub with no .py beside it is expected
reportMissingModuleSource = "none"
```

stubgen does not edit `.gitignore`. Ignoring the stubs keeps ruff from linting them and
leaves one file per component. Committing them is allowed, and `--check` keeps them
honest. In CI, regenerate and then check types, or check committed stubs:

```sh
python -m pyjinhx.stubgen app && pyright   # stubs ignored by git
python -m pyjinhx.stubgen app --check      # stubs committed
```

`reportMissingModuleSource = "none"` is global, so it also hides the warning for
third-party stub-only packages. The alternative is to live with one warning per import of
a `.pjx` module.

What a stub keeps and drops:

- **Annotate return types in blocks.** A stub keeps no function bodies, so an unannotated
  `def` is `Unknown` for the type-checker.
- `__init__` bodies are kept verbatim, since their `self.x = ...` lines declare
  attributes. Every other body becomes `...`.
- **Imports in a block are not re-exported** by its stub. Import a name from the module
  that defines it, never through the component's module.
- Stricter Pyright modes (`strict`, `reportUnusedImport`) flag the stub's `...` statements
  and unused imports. Keep the stubs resolvable but unchecked with Pyright's `ignore`
  setting, scoped to your components: `ignore = ["app/components/**/*.pyi"]` under
  `[tool.pyright]`. `ignore` suppresses diagnostics for those files and still uses them to
  resolve imports. (`exclude` behaved the same in a test with basedpyright, but `ignore`
  says what you mean.)
- The generator skips hidden directories, virtualenvs (any directory with a `pyvenv.cfg`),
  `site-packages`, `dist-packages`, `build`, `dist`, `__pycache__` and `node_modules`, and
  writes no stub for a block that a `.py` module or package shadows.

A library that ships `.pjx`-hosted classes must ship the generated stubs in its wheel.

### Editor tooling

pyjinhx is the single source of pjx facts for editors. All three forms parse and never
import or run application code, so they are safe on an untrusted workspace:

- `python -m pyjinhx.manifest` prints every component under the paths as JSON, or one
  unsaved buffer with `--stdin --filename`.
- `python -m pyjinhx.manifest --grammar` prints the versioned block grammar,
  `pyjinhx/block_grammar.json`.
- `tests/fixtures/block_grammar/` in the repository is a corpus of documents with the
  result a scanner must give, for editors that implement their own scanner.

See [the command reference](../reference/commands.md#python-m-pyjinhxmanifest).

### Known limits of shape P

- **A line that is only `{#python` in column 0 makes the file a
  document**, wherever it sits, including an example inside a `<pre>`. `setup()` imports
  it and fails with "no component class is named for ...". Indent the example, or wrap it in
  `{% raw %}...{% endraw %}`, which is not a document. A prose comment that continues the
  line, such as `{# python helpers below #}` or `{#python is nice #}`, a spaced
  `{# python`, an indented `{#python`, or one mid-line, is a plain comment.
- **`setup()` does not import a plain `.py` subclass of a document's class.** Something
  in your application must import it, or the subclass is never registered.
- **Importing a `.pjx` runs its Python**, and `setup()` imports every block document under
  `components_root`. A template was already trusted code (a header's dotted name imports a
  module); this makes it plain. Never point `components_root`, or an import path, at files
  a user can write. The manifest, stubgen and `pyjinhx.sfc` only parse.
- **coverage.py** cannot parse a `.pjx` for its report. Omit `*.pjx`, or accept the
  warning.
- **ruff** reads `.py` files, so it does not see a block, and it has no `.pjx` formatter.
  To lint the blocks, extract the Python with `pyjinhx.sfc.python_source` (an internal
  helper, not public API) and pipe it in; line numbers stay right and the reported name
  ends in `.py`:

  ```python
  # lint_blocks.py: python lint_blocks.py app
  import subprocess
  import sys
  from pathlib import Path

  from pyjinhx.sfc import python_source

  status = 0
  for path in sorted(Path(sys.argv[1]).rglob("*.pjx")):
      code = python_source(path.read_text(encoding="utf-8-sig"), str(path))
      if code is not None:
          cmd = ["ruff", "check", "--stdin-filename", str(path.with_suffix(".py")), "-"]
          status |= subprocess.run(cmd, input=code, text=True).returncode
  sys.exit(status)
  ```

- **Type-checking a block's own body** happens in the editor. In CI only the block's
  signatures are checked, through the stub.
- **`pkgutil.iter_modules` and `walk_packages` do not list `.pjx` modules**, because they
  never ask a meta-path finder. A registry that discovers modules by walking a package, or
  by `rglob("*.py")`, misses them; `setup()` does not.
- **Zip and frozen `sys.path` entries** never match: the finder reads files from disk.
- **`python -m app.ui.card`** runs the block with `__file__` set to the `.pjx`, but through
  `runpy` as `__main__`: the stem-class check does not run and the class is not
  registered.
- **`importlib.reload(module)`** runs the block again and makes new classes that nothing
  else references. It is not a reload mechanism.
- A `card/` directory next to `card.pjx` shadows it, and so does a `card.py`; `setup()`
  refuses both.

### Folding existing components

`scripts/fold_components.py` in the pyjinhx repository does the mechanical moves. It is
a repo script, not public API. Every subcommand is a dry run that prints a diff and a
summary; add `--write` to apply it. Only files under the paths you pass are touched.

    uv run python scripts/fold_components.py assets app/components --root app
    uv run python scripts/fold_components.py template app/components --write
    uv run python scripts/fold_components.py declass app/components --root app
    uv run python scripts/fold_components.py pyblock app/components --root app

| Command | Move | Refuses when |
|---|---|---|
| `assets` | sibling `.css`/`.js` into a `{#css#}`/`{#js#}` block of the template beside it | the text contains `#}`; a subclass with its own template inherits the asset; a subclass that renders the template has its own sibling file of that kind; the template already has that block; the class's `template` is not a triple-quoted literal that can hold it |
| `template` | a class's adjacent `.pjx` into `template = r"""..."""` (S to C) | the class already assigns `template`; the text holds both triple-quote styles or ends in a backslash; indentation would change when read back |
| `declass` | a fields-only class into a `{#def#}` header, deleting the `.py` (S to T) | the class has methods, decorators, other bases or other statements; a type or default is not expressible in a header; a default is a call, which a class runs once and a header would run per instance; a `Field(...)` with constraints such as `min_length`, which a header cannot express; the module holds more than the class and imports; another class under the paths or `--root` subclasses it (a header-only component has no class to import) |
| `pyblock` | a class's module into a `{#python` block at the top of its `.pjx`, deleting the `.py` (S to P) | the module's source contains `#}`; no class snakes to the module's stem, or more than one does, or it is an `__init__.py`; the class assigns its own `template`; there is no `.pjx` beside it; the `.pjx` already has a block or a `{#def#}` header; a `card/` directory would shadow the `.pjx` |

After `pyblock`, the script reminds you to put `import pyjinhx` in the root package's
`__init__.py` and to regenerate the [stubs](#stubs-and-type-checking). It reports, without
refusing, other component classes in the module that keep their own `.pjx` and every line
under `--root` that names the deleted `card.py`; a module that mentions `__file__` or
`__main__` is flagged because `__file__` becomes the `.pjx`. After writing, it re-reads the
result and checks that the block is the module's source and the markup is unchanged.

`declass` prints every remaining reference to a folded class name, and `assets` every
line that still names a folded file (`card.css`), in any file type, because both report
rather than rewrite (`--root` says where to look, and the summary counts the
references). Code that builds an asset path by hand breaks once the file is gone. The folded component also
becomes permissive: undeclared attributes that the class rejected now pass through
(see the shapes above). The script exits 1 if it
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

If several files share a tag (same stem in different directories), only the headed
ones count: exactly one headed file answers the tag, and two or more make it
ambiguous, raising `LookupError` naming them. Rename all but one, or call
`component("Name")` to pick the first. A class you declare always wins over a
template.

The set of orphan templates is taken when the registry is built, and each is read
once, on its tag's first miss. Adding a header to a template that has already been
found headerless, or adding a new `.pjx`, takes effect after a restart or another
`setup()`. Editing the markup of a template that is already a component is picked
up as usual.

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
  must touch `{#` (`{#css`, not `{# css`) and end its line, with the body starting on
  the next one. A prose comment such as `{# css tweaks #}` or a one-line
  `{#js hack: remove later #}` therefore stays a plain comment. Like the `{#def#}`
  header, a block never appears in the rendered output, and the template still
  renders in plain Jinja.
- `{#def ... #}` may sit on one line, so any comment that starts with `{#def ` (no
  space after `{#`) is read as a header. Keep a prose comment about defaults spaced:
  `{# def... #}` only counts as a header when it is the very first thing in the
  document.
- A block can sit anywhere in the document, in any order relative to the `{#def#}`
  header. It is read statically: putting it inside `{% if %}` does not make it
  conditional. A `{#python` inside `{% raw %}` is sample text, not a block.
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
- The two inherit differently. A subclass's own sibling `.css` replaces its parent's
  `.css` file, but not a `{#css#}` block in the parent's template it renders: that
  subclass ships its own file **and** the parent's block.
- `AssetMode.LINK` has no file to point a URL at, so a component with a block raises
  `ValueError` in LINK mode. Use `INLINE`, or `NONE` with a bundle: `all_assets()`
  lists each block as a path such as `ui/card.pjx#css`, and `read_text()`/`read_bytes()`
  on it return the block body, so the [one-bundle](assets.md#one-bundle-deployment)
  recipe works unchanged. Those two are all it supports: it names no real file, so
  `open()`, `stat()` and file copies fail on it.

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