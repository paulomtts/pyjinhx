# Single-file components for v2 — candidate formats and mechanics

Status: draft for maintainer review. This is the detailed background for the
class-in-one-file shape ("Shape C"). The unified design it belongs to is
`docs/superpowers/specs/2026-11-25-fewer-files-design.md`; the ADR draft is
`docs/superpowers/rebuild/adr/0014-a-component-is-a-pjx-document.md`; the
build order is `docs/superpowers/plans/2026-11-25-fewer-files.md`.

## Problem

A large consumer app has hundreds of components, each spread over up to four
files: `card.py`, `card.pjx`, `card.css`, `card.js`. Reading or changing one
component means opening four tabs, and the directory listing is four times
longer than the component list. The maintainer wants one file per component.

v0.x had an answer — a `{# python #}` block at the top of a `.pjx` file, loaded
through an import hook — and ADR 0008 dropped it from v2. Its objections are the
acceptance criteria for anything that replaces it:

1. **Exec at discovery.** Embedded Python had to be extracted and `exec`-ed by
   pyjinhx's own loader.
2. **LSP / type-checker coupling.** Python living in a non-`.py` file is
   invisible to pyright, ruff, IDE navigation and refactoring unless stubs are
   generated and kept fresh, and pjx-ls had to host a Python language service.
3. **Opaque code placement.** Import semantics, `__file__`, tracebacks and
   debuggers all had to be taught about code that is not where Python expects
   code to be.

Two pieces of parallel work bound the scope. Inline `{# css #}` / `{# js #}`
blocks inside a template, and wider use of `{#def#}`-headed classless
templates, already give a one-file answer for components with **no Python
logic**. What is left is the component that needs a class — a `load()`, a
validator, a computed property, reactive keys — and still wants one file.

## Candidates

### A. `.pjx` host, `{# python #}` block, import hook (v0.x, modernised)

```jinja
{# python
class Counter(BaseComponent):
    remaining: int
#}
<div>{{ remaining }} left</div>
```

The v0.x design with its rough edges filed down: `ast` validation before
running the block, line-padded compilation so tracebacks point at the `.pjx`,
a `sys.meta_path` finder so `from app.counter import Counter` works.

- Exec: still a custom loader compiling and running code out of a template
  file. A meta-path finder is "normal import semantics" only in the narrowest
  sense; it runs on every import in the process and must arbitrate `.py` vs
  `.pjx` collisions.
- Tooling: pyright/ruff/mypy do not read `.pjx`. Needs generated `.pyi` stubs
  (v0.x: `python -m pyjinhx.stubgen`, a gitignored cache, an `extraPaths`
  entry, a `--check` step in CI). Stubs carry signatures only, so go-to-
  definition lands in a stub, rename-symbol does not reach the real code, and
  ruff never lints the block.
- Template tooling: excellent — the file is a template first.

### B. `.pjx` host, generated shadow `.py`

Same file format as A, but a build step (`pjx build`, or a watcher in dev)
writes a real `counter.py` next to it — or into a shadow package — containing
the block's code plus a line-number comment map. Python imports the generated
module; no hook.

- Exec: none beyond importing a real `.py`.
- Tooling: type-checkers see real code, but it is *generated* code. Edits made
  through the IDE (quick-fix, rename) land in the wrong file and are
  overwritten. Diagnostics point at the shadow file unless every tool is
  taught the map. A stale shadow is a new class of bug; committing the shadows
  doubles the file count the feature exists to reduce; not committing them
  makes a build step mandatory before the first import, including in CI and
  in the type-checker's own run.
- Template tooling: excellent.

### C. `.py` host, inline template (recommended)

```python
from pyjinhx import BaseComponent


class Counter(BaseComponent):
    remaining: int = 0

    template = """
    <div class="counter">{{ remaining }} left</div>
    """
```

The component is an ordinary Python module. The one new thing is that the
class may carry its template as a string instead of pointing at an adjacent
`.pjx` file.

- Exec: none. The module is imported by Python, like every class-based
  component today. pyjinhx reads the template back out of the module's own
  source file with `ast` — a parse, never an exec.
- Tooling: nothing to do. The class is real Python in a real `.py`; pyright,
  ruff, the debugger, rename and go-to-definition work with no stubs, no
  config, no generated files.
- Template tooling: this is where C pays. The markup is inside a Python
  string, so highlighting and template diagnostics need editor language
  injection (see "Editor story" below).

### Comparison

| | A: `.pjx` + hook | B: `.pjx` + shadow `.py` | C: `.py` + inline template |
|---|---|---|---|
| Exec outside Python's own import | yes | no | no |
| Custom importer in `sys.meta_path` | yes | no | no |
| Type-checker / linter on the class | via stubs, signatures only | on generated code | native |
| Rename / go-to-definition | broken or stub-only | lands in generated file | native |
| Build or generation step | stub generation | mandatory | none |
| Extra files on disk | stub cache | shadow modules | none |
| Template highlighting / pjx-ls | native | native | needs injection |
| Tracebacks at the right line | yes (padding) | needs a map | yes (padding) |
| Several components in one file | no | no | yes |
| New machinery in pyjinhx | finder, loader, splitter, stubgen | splitter, generator, watcher | one `ast` lookup |

### Recommendation: C

The three ADR 0008 objections are all about Python living somewhere Python
tooling cannot see. A and B keep the code there and spend machinery
compensating. C moves the *template* instead — the half whose tooling is
optional. If template highlighting is missing the developer loses colours; if
Python tooling is missing the project loses type-checking in CI. Degrading the
cheap side is the better trade, and it is the only candidate that adds no
build step, no importer and no generated artefact.

C also is not a "fourth component shape" in ADR 0008's sense. It is the
existing class-plus-template shape with the template's location generalised:
adjacent file *or* class attribute. Resolution, the registry, slots, caching
and assets are untouched.

## The format

```python
from pyjinhx import BaseComponent


class Badge(BaseComponent):
    label: str
    count: int = 0

    @property
    def is_empty(self) -> bool:
        return self.count == 0

    template = """
    <span class="badge">{{ label }} ({{ count }})</span>
    """
```

Rules:

1. `template` is a class attribute holding one plain string literal. `"""`,
   `'''`, raw (`r"""`) and single-line strings are all fine. f-strings,
   concatenation, names and calls are not: the template must be readable from
   the source text alone. Violations raise at first render with the file and
   line of the assignment.
2. No annotation is needed. `BaseComponent` declares
   `template: ClassVar[str | None] = None`, which is what lets pydantic accept
   the bare assignment (the same mechanism `auto_id = False` relies on).
3. The string is a **pjx document** — exactly what the adjacent `.pjx` file
   would contain. Anything a `.pjx` file may hold, the string may hold,
   including the inline `{# css #}` / `{# js #}` blocks from the parallel work
   once they land.
4. Leading blank lines and common indentation are removed, so the template
   may be indented with the class body or written flush left.
5. A class with an inline `template` uses it; its adjacent `.pjx`, if one
   still exists, is ignored. (Open question 3: warn?)
6. Any number of components may live in one module. Each class's tag is still
   its snake_cased class name; the module's filename is irrelevant to
   inline-template components.
7. Use a raw string when the template contains backslashes (inline scripts,
   regexes). A non-raw string is read as Python reads it, and an escape such
   as `\n` both changes the markup and shifts the line numbers reported for
   everything after it.

## How it works

### Resolution

The MRO walk that picks a class's template (`_walk_template`, ADR 0007/0010)
gains one check per ancestor, before the existing file probe: *does this
class's own `__dict__` hold a `template` string?* If so, that ancestor owns
the template and the walk stops. The check is a dict lookup — no filesystem
access — so ADR 0007's probe budget is unchanged.

Because the check sits inside the existing walk, inheritance needs no new
rule:

- `class Danger(Button)` with no template of its own renders `Button`'s
  inline template (nearest ancestor wins, as today).
- A subclass with its own inline `template` or its own adjacent `.pjx`
  overrides the parent, whichever kind the parent uses.

The result is recorded on `ClassDescriptor`:

- `template_path` — the `.py` file of the module that defines the owning
  class.
- `inline_class` — the owning class's name; `None` for a `.pjx` template.

Keeping `template_path` a real file on disk is deliberate. Everything that
already reads it keeps working without knowing inline templates exist: the
render cache's mtime-based key, discovery's "this class has a template of its
own" test, the loader's freshness check, the provenance map.

### Extraction — `ast` only

`pyjinhx/sfc.py` holds one function: given a module's source text and a class
name, return that class's template. It parses the source with `ast`, finds
the `ClassDef`, finds the assignment to `template`, and requires its value to
be a string constant. Nothing is compiled or executed, and it never touches
the imported class — which is why it also serves hot reload (below).

It is called from the Jinja loader, lazily, the first time a component
renders and again only when the file's mtime changes. The template name
handed to Jinja is `<absolute path>::<ClassName>`; the loader splits on `::`
and returns the `.py` path as the template's filename.

### Line numbers

The extracted template is prefixed with a Jinja comment containing exactly as
many newlines as there are lines above the template's first line in the
`.py` file:

```
{#⏎⏎⏎⏎⏎⏎⏎#}<span class="badge">…
```

A comment emits nothing, so the rendered markup is unaffected, but Jinja
counts its newlines. Line *N* of the template as Jinja sees it is therefore
line *N* of the `.py` file. Combined with the filename the loader reports:

- `TemplateSyntaxError` carries the `.py` path and the true line.
- Runtime errors inside a template (`UndefinedError`, a failing filter) show
  a traceback frame `File ".../badge.py", line 12, in top-level template
  code`, and because that file and line really exist, the traceback prints
  the offending template line.
- Editors that parse tracebacks jump to the right place.

This is the v0.x padding trick pointed the other way, and it removes the need
for any source map. pjx-ls can use the same identity mapping for an embedded
region: positions in the virtual template document equal positions in the
`.py` file, line for line.

### Hot reload

Jinja already re-checks a template's mtime on lookup (`auto_reload`), and the
loader's `uptodate()` already stats `template_path`. For an inline template
that path is the `.py` file, so saving the file invalidates the compiled
template and the next render re-extracts it from the new source — without
re-importing the module. A template-only edit is picked up by a running
process exactly as a `.pjx` edit is today.

Edits to the Python half need a re-import, as they always have. In practice
most dev servers watch `*.py` and restart the process on any save, so an
inline-template edit typically costs a restart where a `.pjx` edit costs
none. That is a real regression in the edit loop for template-only changes;
see open question 4.

### Registry and discovery

No change. An inline-template class is a class-based component: it is known
once its module is imported, it is offered to `build_registry` with every
other subclass, and `_has_own_template` answers true because `template_path`
is an existing file. `<Badge/>` in any template resolves through the same
tag → class map.

Discovery's `.pjx` walk does not look at `.py` files and does not need to.
Nothing is found by scanning; there is no discovery-time parsing of Python at
all.

### Assets

Adjacent `badge.css` / `badge.js` keep resolving through the unchanged MRO
asset walk, so a component can move its template inline first and its assets
later.

The single-file end state is the inline template carrying `{# css #}` /
`{# js #}` blocks. That needs no design here beyond one constraint on the
parallel work: **whatever extracts those blocks must take its source from the
template loader (or `sfc.extract_template`), not from
`descriptor.template_path.read_text()`** — for an inline template that path
is a Python file. With that seam respected the two features compose with no
further code: the string is a pjx document, and blocks are part of a pjx
document.

`{#def#}` headers compose the same way they do today: a class is registered,
so a header in its template is stale and is reported by the existing warning.
(The prototype does not yet probe inline templates for a stale header.)

### Render cache

The cache key includes `template_path`'s mtime. For an inline template that
is the module's mtime, so any edit to the file — template or Python —
invalidates the class's cached levels. Slightly coarser than necessary,
never stale.

## Editor story

Python: native, nothing to configure.

Template inside the string:

- **VS Code**: the pjx extension ships a TextMate injection grammar that
  scopes the contents of `template = """…"""` inside a Python class as pjx.
  Grammar-only; no language server involvement.
- **JetBrains**: language-injection rule on the same pattern, or a
  `# language=Jinja2` comment above the assignment.
- **Neovim / Helix**: a tree-sitter injection query on the assignment.
- **pjx-ls** (optional, later): treat the string as an embedded document.
  Thanks to the identity line mapping this is "blank out everything that is
  not template" — far lighter than v0.x's requirement that pjx-ls front a
  Python language service.

Until any of that exists the developer sees an uncoloured string. Nothing
breaks, and CI is unaffected.

## Migration from `.py` + `.pjx`

Mechanical and incremental — resolution is per class, so a codebase can be
half-migrated indefinitely.

Planned codemod, `scripts/fold_components.py` (plan task 7):

1. Import the package; for each component class whose template is an
   adjacent `.pjx` it owns, append `template = r"""…"""` as the last
   statement of the class body and delete the `.pjx`.
2. Once inline blocks land: wrap adjacent `.css` / `.js` in `{# css #}` /
   `{# js #}` blocks inside the template and delete those files.
3. Skip and report templates that contain `"""` or end in a backslash.

`unfold` is the same operation reversed, which keeps the decision cheap to
back out of.

v0.x `{# python #}` files migrate by moving the block's code to a `.py` and
the remainder into `template` — the same split the v2 migration guide
already prescribes, minus the second file.

## State of the code on `feat/sfc-v2`

- `pyjinhx/sfc.py` — `extract_template()` with passing tests
  (`tests/pyjinhx/test_sfc_extract.py`).
- `tests/pyjinhx/test_sfc_component.py` — written first and **failing**: it
  is the acceptance test for the resolution, loader and render work, none of
  which is implemented. See the plan's task 5.

## Open questions

1. **Attribute name.** `template` is the obvious word and nothing in the
   repo uses it as a field, but it becomes a reserved class-level name on
   every component. A consumer with a *field* called `template` would break.
   Alternatives: `pjx_template`, `__template__`.
2. **Supersede or amend ADR 0008?** The draft ADR supersedes it. 0008's
   decision ("no `{# python #}` blocks, no exec at discovery") arguably still
   stands in full; an "amends" framing would be equally honest.
3. **Inline template and adjacent `.pjx` both present.** Inline wins
   silently in the prototype. A warning costs one `is_file` probe per
   inline class at registration.
4. **Dev-loop cost.** Should the docs recommend excluding component modules
   from the reloader, or is restart-on-save acceptable for template edits?
5. **Eager validation.** A non-literal `template` is reported at first
   render. Reporting it at class creation would cost an `ast.parse` per
   component module at import time.
6. **Same-named classes in one module.** Extraction finds the first class
   with that name that assigns `template`. Two such classes in one file
   (e.g. inside two functions) are ambiguous; worth an error?
