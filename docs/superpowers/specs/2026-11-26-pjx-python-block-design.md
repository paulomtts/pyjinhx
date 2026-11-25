# A `{#python … #}` block in `.pjx` files — design

Status: draft for maintainer review. Planning only; no code exists yet.
ADR draft: `docs/superpowers/rebuild/adr/0015-a-pjx-document-may-carry-its-class.md`.
Build order: `docs/superpowers/plans/2026-11-26-pjx-python-block.md`.
Editor follow-up (separate repo, later): `docs/superpowers/specs/2026-11-26-pjx-ls-followup.md`.
Builds on: `2026-11-25-fewer-files-design.md` (the one-model design),
`2026-11-25-sfc-v2-candidates.md` (candidates A/B/C), and the trial report
`2026-11-25-fewer-files-trial.md`.

## What is settled

These are maintainer decisions and are not argued here:

- A `.pjx` file may hold its component's Python class in a `{#python … #}`
  block. This is candidate A of the candidates document, which that document
  and ADR 0008 rejected. The reason for reversing is editor tooling: pjx-ls
  owns the whole `.pjx` file the way Vue and Svelte tooling own theirs.
- It sits beside the `.py`-hosted shape (`template = r"""…"""`), which stays.
- The class must be importable from ordinary Python:
  `from app.ui.card import Card` where `Card` lives in `card.pjx`. That needs
  an import hook, and generated `.pyi` stubs so type-checkers see the class.

## The shape

```jinja
{#python
from pyjinhx import ReactiveComponent

from app.todos import Keys, store


class TodoCount(ReactiveComponent, react={Keys.TODOS}):
    remaining: int = 0

    @classmethod
    def load(cls) -> "TodoCount":
        return cls(remaining=store.remaining())
#}
<div class="counter">{{ remaining }} left</div>
{#css
.counter { font-weight: 600; }
#}
```

This is **shape P** (pjx-hosted class). With it there are four shapes:

| Shape | Files | The class lives in | Pick it when |
|---|---|---|---|
| **T** template only | `card.pjx` | nowhere (`{#def#}` header) | props and markup, nothing computed |
| **P** pjx-hosted class | `card.pjx` | the `{#python#}` block | the component needs Python and you edit with pjx-ls |
| **C** py-hosted template | `card.py` | the module | the component needs Python and you want stock tooling |
| **S** split | `card.py` + `card.pjx` | the module | unchanged; long templates, shared assets |

P and C are the same component written two ways. The difference is which half
gets second-class tooling:

| | P (`.pjx` hosts the class) | C (`.py` hosts the template) |
|---|---|---|
| Markup, css, js in the editor | native: highlighting, formatting, diagnostics | a Python string, plain unless an injection grammar is installed |
| Python in the editor | through pjx-ls, forwarded to Pyright (follow-up work; until then, plain text) | native |
| Cross-section features (`{{ field }}` completion, tag props, rename) | possible, one file owns both halves | not planned |
| Type-checking in CI | needs generated `.pyi` stubs | nothing to do |
| ruff, coverage | by extraction, or not at all (see "Tooling gaps") | native |
| Import | through pyjinhx's import hook | Python's own |
| Several components in one file | one document per file; extra classes allowed | yes |
| Template-only edit under a `*.py` reloader | no restart | restart |

Rule of thumb for the docs: *use P if your team edits with pjx-ls; use C if
you want every Python tool to work with no setup.* Rendered output, tag, props
and assets are identical, and a project can mix all four shapes per component.

## Block grammar

The document grammar from the fewer-files design gains one keyword:

```
block   := "{#" keyword … "#}"
keyword := "def" | "css" | "js" | "python"
```

Rules for `python`, in the order a scanner checks them:

1. **Opener.** A line that is exactly `{#python`, optionally followed by
   spaces or tabs. The `{#` is in column 0 and the keyword touches it. This is
   the css/js rule plus "starts its line".
2. **Body.** Every line after the opener, up to the closer. It is compiled as
   written: no dedent, no stripping. Module-level code therefore starts in
   column 0, as in a `.py` file. An indented body is Python's own
   `IndentationError`, at the right line.
3. **Closer.** The first `#}` after the opener. It must be alone on its line,
   in column 0 (trailing spaces or tabs allowed).
4. **At most one** `python` block per document. It may sit anywhere, between
   other blocks or markup. By convention, and as the fold script writes it, it
   comes first.
5. **No `{#def#}` header in the same document.** The class declares the props.
6. **Some markup.** A document that has a `python` block and nothing else but
   blocks, comments and whitespace is refused.

The block is an ordinary Jinja comment, like the other three. Plain Jinja
renders the document unchanged and drops the block. Jinja ends a comment at
the first `#}`, so rule 3 is not a choice: a `#}` inside the Python (in a
string, a comment, or `f"{n:#}"`) ends the block early. The scanner sees that
the first `#}` is not alone on its line and raises a `SyntaxError` naming the
line, with the fix (`"#" "}"`, or move the code out). A body line that is
exactly `#}` also ends the block early; the real closer is then left over and
the existing stray-`#}` check reports it.

The v0.x form `{# python` (with a space) is prose in v2 and is not a block.
Importing a `.pjx` whose first line is the v0.x opener raises an `ImportError`
that says to remove the space, because the only other outcome is a
`ModuleNotFoundError` with no hint.

**Alternatives considered for the closer.** v0.x cut the block out before
Jinja saw it and closed it at a line holding only `#}`, so an inline `#}` was
safe. That needs a second document reader that strips Python before every
compile, and it breaks the property that a pjx document is valid Jinja as it
stands. Rejected: one grammar, one scanner rule, and the failure is loud.

### Line numbers are the file's

Nothing is moved, so no source map exists anywhere:

- **Markup.** The block is a comment whose newlines Jinja counts. Template
  line N is file line N, as for css/js blocks today.
- **Python.** The body is compiled after padding it with one newline per line
  above it, with the `.pjx` path as the filename. Code line N is file line N,
  and because nothing is dedented, column N is column N.

So a `SyntaxError`, a traceback frame, a `breakpoint()`, a Jinja error and a
Pyright diagnostic on the virtual document all name the real file, line and
column. Tracebacks print the offending line because `linecache` reads the
`.pjx` file from disk by that name; nothing has to be registered.

## How the class and the markup bind

**The markup belongs to the class whose snake_case name is the file's stem.**
`todo_count.pjx` belongs to `TodoCount`. This is ADR 0007's rule, and it needs
no new resolution code: the module's `__file__` is the `.pjx`, so the existing
probe `<module dir>/<snake name>.pjx` lands on the module's own file.
`_walk_template` is not touched. `ClassDescriptor.template_path` is the `.pjx`
and `inline_class` stays `None`, so the Jinja loader, `InlineAsset`, the render
cache key and sibling `.css`/`.js` resolution all work as they do for shape S.

The block is a module, so it may hold anything a module may:

- imports, constants, helper functions, non-component classes;
- **more component classes.** Each resolves its template the usual way. A
  subclass with no template of its own (`class TaskNameField(NameField)`
  inside `name_field.pjx`) inherits the document. A class that wants its own
  markup needs its own file.

Refusals, each with the file and line:

| Situation | Raised | When |
|---|---|---|
| No component class named for the stem | `ImportError` | import |
| Two classes that snake to the stem (`HTTPCard`, `HttpCard`) | `ImportError` | import |
| A class in the block assigns `template = "…"` | `ImportError` | import |
| `{#def#}` header in the same document | `TypeError` | class creation |
| No markup | `TypeError` | class creation |
| The document has a `python` block but its class comes from another file | `TypeError` | class creation |

The last row is the `.py` clash, described next.

**Alternatives considered for binding.** (1) An explicit marker
(`__pjx_component__ = Card`): v0.x had it and removed it in its last commit.
(2) "The only component class in the block" (v0.x's final rule): forbids
subclass families and helper components in one file, which the consumer app
has (`NameField` and six subclasses). (3) By name: chosen. It is the rule
every other shape already follows, and tag = stem = class stays true.

## Import

### Module identity

`app/ui/card.pjx` is the module `app.ui.card`, found on its parent package's
`__path__` exactly where `card.py` would be found. A `.pjx` is always a plain
module, never a package (there is no `__init__.pjx`).

### The hook

A `sys.meta_path` finder, `pyjinhx.importer.PjxFinder`, **appended to the end**
of `sys.meta_path`. Python asks it only for a name every other finder failed
to find, so ordinary imports pay nothing. For such a name it looks for
`<entry>/<last segment>.pjx` on the search path it was given, reads the file,
and answers only if it holds a `python` block. A `.pjx` without one is not a
module, and the import fails with Python's own `ModuleNotFoundError`.

The loader compiles the padded body (see "Line numbers") and runs it as the
module body through Python's normal loader protocol:

- `module.__file__` is the `.pjx` path; `__spec__`, `__package__`, relative
  imports and `sys.modules` behave as for a `.py` file;
- `get_source()` returns the padded Python, `get_code()` works, so
  `python -m app.ui.card` and `inspect` on functions work;
- no bytecode is cached. Blocks are small and compiled once per process. The
  trial measures the cost; caching is added only if that number is bad.

After the body runs, the loader checks the three import-time refusals above
and records the document as loaded (path, module name, document class).

**Alternatives considered.**

| | A. Finder appended to `sys.meta_path` (chosen) | B. Replace the path hook (`FileFinder` with a `.pjx` loader) | C. Generated shadow `.py` |
|---|---|---|---|
| Cost on normal imports | none | none | none |
| Touches global import state | one extra finder | rebuilds `sys.path_hooks` from private details, clears the importer cache | nothing |
| Build step before first import | no | no | yes, in dev, CI and the type-checker's own run |
| Type-checker sees the class | via stubs | via stubs | natively, but in a generated file |
| Edits and quick-fixes land in | the `.pjx` (pjx-ls) | the `.pjx` | the wrong file |
| Stale artefact can change behaviour | no (a stale stub only misleads the type-checker) | no | yes |
| Files on disk per component | 1 (+1 ignored stub) | 1 (+1 ignored stub) | 2 |

B is the most "native" at run time but depends on
`importlib.machinery._get_supported_file_loaders`, a private function, and
gains nothing A lacks. C was candidate B of the candidates document and is
rejected for the reasons given there; it also makes the generated copy the
thing Python runs, so a forgotten regeneration is a behaviour bug, not a
typing one. A fourth option, a `pyjinhx.load("card.pjx")` function with no
import hook, fails the importability requirement.

### A sibling `card.py`

Python finds `card.py` first, so the finder is never asked and cannot refuse
the pair itself. `card.py` + `card.pjx` is also shape S, so the pair is only
wrong when the `.pjx` has a `python` block. Neither file wins; it is refused,
in three places:

1. **Class creation.** `_resolve_class_descriptor` already reads the document.
   If it has a `python` block and the class that owns the template was not
   defined by that file, it raises: two classes claim one document. This
   catches `card.py` defining `Card` next to a `card.pjx` that also does.
2. **Startup.** `setup()` imports every `python`-block document under
   `components_root` (see "Discovery") and checks the module it got back has
   that file as `__file__`. A sibling `card.py` or `card/` directory that
   shadows it fails there, naming both.
3. **`python -m pyjinhx.stubgen --check`**, statically, for CI.

A `.py` file that *subclasses* a `.pjx`-hosted class is fine and common.

### When the hook is installed

On `import pyjinhx`. `pyjinhx.importer` is stdlib-only, so this adds no weight
to the lazy package import. `install()` is idempotent and `uninstall()` exists
for tests.

The consequence is one line the user must write: **pyjinhx has to be imported
before the first `.pjx` module is.** A block starts with `from pyjinhx import …`,
but the hook is needed to *find* the block. In practice the root package's
`__init__.py` gets `import pyjinhx`, which covers the app, pytest, `python -m`,
uvicorn's reload subprocess and unpickling in a worker. The docs say so, and
the fold script prints it.

**Alternatives considered.** A `.pth` file shipped in the wheel would install
the hook at interpreter startup and remove that line. It also runs in every
interpreter of the environment whether or not it uses pyjinhx, is invisible,
and is fragile under editable installs. Rejected. An explicit
`pyjinhx.install_import_hook()` call was rejected as the same line with more
typing.

### What works and what does not

| | Status |
|---|---|
| `from app.ui.card import Card`, relative imports, `__init__.py` re-exports | works |
| Pickle, `copy.deepcopy` | works: classes pickle by `module.qualname`, and both are real |
| `python -m app.ui.card` | works (parents are imported first, which installs the hook) |
| pytest | works; `.pjx` files are not collected or assertion-rewritten |
| `importlib.util.find_spec` | works |
| `pkgutil.iter_modules` / `walk_packages` | does **not** list `.pjx` modules (it never asks meta-path finders) |
| `importlib.reload(module)` | runs, and makes new classes that nothing else references; not a reload mechanism |
| `inspect.getsource(function)` | works (same lines) |
| `inspect.getsource(module)` | returns the whole `.pjx`, not just the Python |
| Namespace packages (no `__init__.py`) | importable by hand; not auto-imported by discovery |

## Discovery

**Discovery never compiles or runs a block. It imports the module by name,
through the hook, like any other code would.**

Two entry points share one function,
`importer.import_document(path) -> module`:

1. If the importer has already loaded that file (under any name), return that
   module. This is how a document the app imported itself is never imported
   twice.
2. Otherwise derive the module name: walk up from the file while the
   directory has an `__init__.py`; the dotted path below the first directory
   without one is the name. This is the rule pytest uses, and it is the only
   rule under which a file has exactly one name.
3. `importlib.import_module(name)`, then check `module.__file__` is the file.
   A mismatch is the shadowing error above. A derived name that does not
   import (the top directory is not on `sys.path`) is an `ImportError` that
   says to import the module before `setup()`.

**At startup (`setup()`), eagerly.** `config._register_components` becomes:
build the registry; import every `python`-block document under
`components_root`; if any import defined new classes, build the registry
again. The first build makes `component("X")` usable by code those imports
run (the consumer app calls it at module level). `discovery.py` itself still
opens no file; the sniff (`"{#python" in text`) lives in `config`.

Why eager: a class-based component has always been known at startup. Reactive
fan-out, `all_assets()`, `dev.dependency_graph()` and consumers' meta-tests
all enumerate `BaseComponent` subclasses, and a block's import error belongs
at startup, not in the middle of a request. The cost is one read of each
`.pjx` under the root per `setup()` call; the trial measures it.

**On a tag miss, lazily.** `classless.component_for_tag` and `component()`
already read an orphan template to look for a header. If they find a `python`
block instead, they call `import_document` and register the document class
with `discovery.register_class`. This covers a file created while the server
runs, and code that calls `component("X")` while startup is still importing.
A class imported this way after startup is not reactive-registered for
fan-out in other workers until restart; `reactive/fanout.py` is left alone.

**Alternatives considered.** Lazy only: no startup reads, but reactive
components unknown to a worker that never rendered them, incomplete asset
collection, and import errors mid-request. Sniffing inside `build_registry`:
breaks discovery's "the walk opens no file" contract for no gain.

## Composition with everything else

- **`{#def#}`**: refused in the same document (rule 5). Shape S only warns
  about a stale header because the two files are edited apart; here both
  declarations are on one screen and tooling would have to pick one.
- **`{#css#}` / `{#js#}`**: unchanged. `hide_block_lines` learns the `python`
  keyword so the block's own line renders as nothing, which is what makes
  shape P byte-identical to shape S. Sibling `card.css` / `card.js` resolve
  through the unchanged asset walk (the v0.x co-located-assets bug cannot
  occur: the module's directory is the document's directory).
- **Inheritance.** A `.pjx` class subclassing another `.pjx` class imports it
  like any module. A `.py` subclass of a `.pjx` class inherits its document
  through the unchanged MRO walk. A subclass with its own file overrides.
- **Reactive registration** happens at class creation, which is now import
  time through the hook. Nothing special.
- **Render cache.** Identity is `module.qualname`, both real. The key's
  template mtime is the `.pjx` mtime, so any edit to the file invalidates the
  class's cached levels, including a Python edit that has not been applied
  yet. Coarser than needed, never stale.
- **Pickling**: see the table above.

## Hot reload, honestly

| Edit | Without a restart |
|---|---|
| Markup, `{#css#}`, `{#js#}` | picked up on the next render (Jinja `auto_reload`, mtime-checked loader), as today |
| The `python` block | **not** picked up. The process keeps the class it imported |

pyjinhx does not reload modules. Re-running a block makes a second class with
the same name while every importer still holds the first.

Two things keep this from being a trap:

- When the Jinja loader re-reads a changed document, it compares the `python`
  block's text with the text that was imported and logs one warning per file:
  "card.pjx: the Python block changed since it was imported; restart to apply
  it." Without this, a markup edit would show and a Python edit silently
  would not.
- The docs give the two dev setups: watch `*.py` only (template edits are
  instant, block edits need a manual restart, and the warning says so), or
  `uvicorn --reload --reload-include '*.pjx'` (every `.pjx` save restarts,
  like shape C).

## Type-checking: stubs

Type-checkers do not read `.pjx`. `python -m pyjinhx.stubgen <paths>` writes
`card.pyi` **next to** each `card.pjx` that has a `python` block.

- **Adjacent, not a cache directory.** v0.x started with a `.pjx/stubs/` tree
  wired through `extraPaths` and had to move (its commit `af337361`): Pyright
  resolves `app.ui.card` inside the real `app/ui/` package and does not merge
  a second tree into it. Adjacent stubs need no `extraPaths` and no
  `stubPath`.
- **Line-preserving.** The stub is the padded Python with each function body
  replaced by `...` in place. Every `class`, `def` and field keeps its line
  number, so "go to definition" from any `.py` file lands on the right line
  of `card.pyi`, and pjx-ls can redirect it to the same line of `card.pjx`
  without a map.
- **Marked.** The opener's line holds
  `# pyjinhx.stubgen: generated from card.pjx; do not edit`. stubgen only
  overwrites or deletes files carrying that marker, and refuses to overwrite
  a hand-written `.pyi`.
- **Pruned.** A marked stub whose `.pjx` is gone or lost its block is deleted.
- **`--check`** writes nothing and exits 1 listing stale, missing and orphaned
  stubs and any `card.py` / `card/` that shadows a block.
- stubgen parses; it never imports or runs the block.

Recommended setup, for the docs:

```gitignore
# generated by `python -m pyjinhx.stubgen`
app/ui/**/*.pyi
```

```toml
[tool.pyright]
reportMissingModuleSource = "none"   # a stub with no .py beside it is expected
```

```sh
python -m pyjinhx.stubgen app && pyright      # CI, stubs ignored
python -m pyjinhx.stubgen app --check         # CI, stubs committed
```

Ignoring the stubs is the recommendation: ruff skips ignored files, so the
generated stubs are not linted, and the file count stays at one per
component. stubgen does not edit `.gitignore` (v0.x did; it is the user's
file). Committing them is allowed and `--check` keeps them honest.
`reportMissingModuleSource` is global, which also hides the warning for
third-party stub-only packages; the alternative is to live with warnings.
pjx-ls is expected to regenerate on save (follow-up).

A library that ships `.pjx`-hosted classes must ship the generated stubs in
its wheel. pyjinhx's own builtins stay shape S in this change.

## Facts for editors: pyjinhx is the single source

pjx-ls is meant to forward to existing language services and add a thin
pjx-only layer. Every pjx-specific fact it needs therefore comes from pyjinhx,
in three forms. All three are parse-only: **no application code is imported or
run**, so they are safe in an untrusted workspace and work on a broken tree.

### 1. The manifest

`python -m pyjinhx.manifest <paths…>` prints one JSON document describing
every component under the paths. `--stdin --filename app/ui/card.pjx`
describes one unsaved buffer instead (this is the "check" mode an editor
calls on each change). There is no console script: the editor must run the
project's interpreter anyway, and a `pjx` on `PATH` may belong to another
environment.

```json
{
  "manifest_version": 1,
  "grammar_version": 1,
  "components": [
    {
      "tag": "TodoCount",
      "kind": "pjx-python",
      "document": {"path": "app/ui/todo_count.pjx", "markup_lines": [13, 13]},
      "blocks": [
        {"keyword": "python", "open_line": 1, "body_lines": [2, 11], "close_line": 12},
        {"keyword": "css", "open_line": 14, "body_lines": [15, 15], "close_line": 16}
      ],
      "class": {
        "module": "app.ui.todo_count", "qualname": "TodoCount",
        "path": "app/ui/todo_count.pjx", "line": 7, "column": 6,
        "bases": ["ReactiveComponent"],
        "stub": "app/ui/todo_count.pyi"
      },
      "props": [
        {"name": "remaining", "annotation": "int", "required": false,
         "default": "0", "literal_values": null, "slot": false, "children": false,
         "line": 8, "column": 4}
      ],
      "members": [{"name": "load", "kind": "classmethod", "line": 10, "column": 8}]
    }
  ],
  "diagnostics": [
    {"path": "app/ui/card.pjx", "line": 9, "column": 14, "severity": "error",
     "code": "python-block-early-close", "message": "…"}
  ]
}
```

- `kind` is one of `template` (T), `pjx-python` (P), `py-template` (C),
  `split` (S).
- Lines are 1-based. Columns are 0-based UTF-16 code units, which is what LSP
  uses by default.
- `annotation` and `default` are the source text as written. `literal_values`
  lists the members when the annotation is a `Literal[…]` of literals. `slot`
  and `children` are true when the annotation names `Slot` / `Children`.
- For kind `template`, `props` come from the `{#def#}` header's signature
  before any name in it is resolved, and `class` is null.
- For kind `py-template`, `document` is the `.py` path plus the span of the
  string literal's contents.
- `members` lists properties, methods and classmethods, for `{{ … }}`
  completion.
- `diagnostics` carries everything pyjinhx would refuse or warn about that
  can be seen without importing: grammar errors, a Python syntax error in a
  block, `{#def#}` with `{#python#}`, no class named for the file, a block
  with no markup, a shadowing `card.py`, a `template` that is not one plain
  literal, a missing or stale stub.

**What static mode cannot see**, stated in the reference: a class counts as
a component only if a `<snake>.pjx` sits beside its module or it assigns
`template`. A subclass that inherits its template is not listed, and
inherited fields are not in `props` (`bases` names where to look). An
importing mode that fills those in is a possible later addition, behind a
flag, and is not part of this change.

### 2. The grammar as data

`python -m pyjinhx.manifest --grammar` prints `pyjinhx/block_grammar.json`,
a small versioned file: the four keywords; "the keyword touches `{#`";
which keywords must end their line (`css`, `js`, `python`) and which take
whitespace or nothing (`def`); the terminator (the first `#}`, as Jinja
does it); the extra `python` rules (opener in column 0, closer alone on its
line, at most one, not with `def`); and the legacy spaced `{# def` form
(first position only). It also settles two things: **`{#-def`, `{#- css` and
any other whitespace-control form is not a block**, and the v0.x `{# python`
is not a block. The Python scanner is not driven by this file; a test proves
they agree by running the corpus below.

### 3. A shared conformance corpus

`tests/fixtures/block_grammar/` holds small `.pjx` sources, each with an
expected-result JSON beside it (blocks with their line ranges, or the error
code and line). pyjinhx's test suite runs the scanner over it. pjx-ls vendors
the directory at a pyjinhx tag and runs its own scanner over the same files.
It covers, at least: each keyword; prose comments that look like blocks;
`{#-def`; two blocks of one kind; a block before the header; a body
containing `#}`; Python containing `f"{n:#}"` and a `#}` comment line; a
non-ASCII line before a block; CRLF line endings.

### The `{#python` contract, in one place

For the editor, the block means exactly this: the keyword touches `{#` and
ends its line; the terminator is the first `#}`, which must be alone on its
line, and a `#}` anywhere earlier is a reported error, not a guess; lines and
columns map by identity; at most one block, anywhere, opener in column 0;
**no names are implicitly in scope** (the block is a plain module and imports
what it uses, `BaseComponent` included); its module name is the manifest's
`class.module`; and a type-checker sees the class through the adjacent
`card.pyi`, so no mirror `.py` file ever needs to be written into the source
tree.

### The `.py`-hosted form, for the injection grammar

`sfc.py` recognises a template only in these forms, and the reference page
will list them so an editor grammar can match the same set: inside a class
body, `template = <literal>` or `template: <annotation> = <literal>`, where
the literal is one string token (`"…"`, `'…'`, `"""…"""`, `'''…'''`, with an
optional `r`/`R` prefix). Not an f-string, not adjacent literals, not a name
or a call. The last assignment in the body wins. The manifest reports the
literal's span, so a grammar that misses a case degrades to no highlighting,
never to a wrong diagnostic.

## Tooling gaps and what is offered

`python -m pyjinhx.sfc card.pjx` prints the block's padded Python. It is the
bridge to tools that read Python from stdin.

| Tool | Status |
|---|---|
| ruff check | by extraction: `python -m pyjinhx.sfc f.pjx \| ruff check --stdin-filename f.py -`. Line numbers are right; the reported name ends in `.py`. The docs carry a three-line loop for CI |
| ruff format | in the editor, once pjx-ls formats the block on save (follow-up). No command-line formatter: documented gap |
| Pyright / mypy on the block's own body | in the editor through pjx-ls. In CI, only the block's *signatures* are checked, through the stub: documented gap |
| coverage.py | cannot parse a `.pjx` for its report. Documented: omit `*.pjx`, or accept the warning |
| Debuggers | line numbers are right; setting a breakpoint in a `.pjx` needs the editor to allow it (pjx-ls follow-up) |

These gaps are the cost ADR 0008 named. They are accepted for shape P and are
the reason shape C stays.

## Security

A template was already trusted code (a header's dotted name imports a
module). Shape P makes that plain: **importing a `.pjx` runs its Python, and
`setup()` imports every `python`-block document under `components_root`.**
Never point `components_root`, or an import path, at files a user can write.
`pyjinhx.manifest`, `pyjinhx.sfc` and `pyjinhx.stubgen` only parse, so they
are safe to run on an untrusted workspace.

## Migration tooling

`scripts/fold_components.py pyblock <paths>` turns `card.py` + `card.pjx` into
one `card.pjx`: the module's source, verbatim, inside a `{#python … #}` block
at the top, followed by the existing document. `card.py` is deleted. Dry run
by default, `--write` to apply, like the other subcommands.

Refused, with the reason:

- the module's source contains `#}` (names the line);
- no class in the module snakes to the module's stem, or the module is an
  `__init__.py`;
- that class has no `.pjx` of its own beside it (inherited or missing), or it
  assigns an inline `template` (shape C; unfold it by hand first);
- the `.pjx` already has a `python` block, or carries a `{#def#}` header.

Reported, not refused: other component classes in the module that keep their
own `.pjx`; every line under `--root` that names `card.py` by path; a reminder
that the root package needs `import pyjinhx` and that stubs need regenerating.
After writing, the script re-reads the result and checks that the block's
body is the module's source and that the markup is unchanged.

Not included: `C → P` and `P → S` conversions. Nothing needs them yet.

## Validation

- **Parity fixture.** `tests/fixtures/fewer_files/` gains a fourth package,
  `pjx_python/` (shape P), holding every component the split shape has. The
  parity test renders it byte-identical to shape S, with the same assets in
  the same order and the same reactive delta, and checks that an error on a
  known line of a block, and of the markup below it, is reported at that line
  of the `.pjx`. One subclass family lives inside its parent's block and one
  subclass lives in a `.py`, so both inheritance directions are exercised.
- **Consumer trial.** The scratch copy from the first trial is re-run with
  `pyblock` in place of `template`, and on the classes `declass` refused. It
  answers open item 3 of the first trial (a header-only component has no
  importable class): those classes take shape P instead and stay importable.
  The report records conversions, refusals, both test tiers, render parity,
  type-check results with stubs, and `import main` timing against the first
  trial's numbers.

## Decisions taken here (veto any)

1. Finder appended to `sys.meta_path`; installed on `import pyjinhx`; no
   `.pth` file.
2. A sibling `card.py` next to a `python`-block `card.pjx` is refused, never
   resolved in favour of either.
3. The markup binds by name; extra classes in the block are allowed.
4. `{#def#}` plus `{#python#}` is an error; a block with no markup is an
   error; an inline `template` inside a block is an error.
5. `setup()` imports every `python`-block document under `components_root`.
6. Stubs are adjacent, line-preserving, marked, and not auto-ignored.
7. No module reload; a warning when a block changed on disk.
8. The v0.x spaced opener is an import error with a hint, not a silent miss.
9. Editor facts come from one parse-only command, `python -m pyjinhx.manifest`
   (workspace or one stdin buffer), plus a versioned grammar file and a
   shared corpus. No console script, and no importing mode yet.
10. Whitespace-control openers (`{#-def`, `{#- css`) are not blocks.
