# Fewer files per component — unified design

Status: draft for maintainer review. Lands as one PR.
ADR draft: `docs/superpowers/rebuild/adr/0014-a-component-is-a-pjx-document.md`.
Build order: `docs/superpowers/plans/2026-11-25-fewer-files.md`.
Background on the single-file shape (candidates compared, line mapping, hot
reload): `docs/superpowers/specs/2026-11-25-sfc-v2-candidates.md`.

## Problem

A component today is up to four files: `card.py`, `card.pjx`, `card.css`,
`card.js`. The consumer app that prompted this has 382 components, 275 of them
with a `.py` class, 211 sibling `.css` files and 56 sibling `.js` files, many
of them a few lines long.

An audit of those 275 classes splits them three ways:

| Group | Count | What blocks a one-file component today |
|---|---|---|
| Must keep a class | 183 | Nothing can remove the class: 72 reactive, 178 with classmethod factories, 92 with properties or computed fields. They need the template to move *to* the class. |
| Could drop the class, small header gaps ("B-easy") | 31 | `{#def#}` cannot say what the class says. |
| Could drop the class, larger header gaps ("B-hard") | 60 | Same, more of it. |

Across the 91 droppable classes the header gaps are: `Slot` fields (34),
`default_factory` (32), non-literal defaults (23), `ExtraAttrs` (21),
`Literal[...]` (15); 39 classes set `auto_id` at class level.

Three fronts follow from that, and they have to read as one feature:

1. **A richer `{#def#}` header**, plus tags that resolve to header-only
   templates without a `component("X")` call — so the 91 can lose their class.
2. **Inline `{#css#}` / `{#js#}` blocks** — so small sibling assets can move
   into the template. Implemented separately on `feat/inline-css-js-blocks`;
   this design integrates with it and does not change it.
3. **A class that carries its own template** — so the 183 become one file.

## One model

> **A component is a pjx document, optionally owned by a Python class.**

A *pjx document* is markup plus up to three comment blocks:

```jinja
{#def title: str, tone: Literal["info", "warn"] = "info" #}
<div class="note note--{{ tone }}">{{ title }}</div>
{#css
.note { padding: 1rem; }
#}
{#js
console.log("note");
#}
```

- `{#def … #}` — the props, when no class declares them.
- `{#css … #}` — the stylesheet.
- `{#js … #}` — the script.

Every block is an ordinary Jinja comment, so plain Jinja renders a pjx
document unchanged and drops the blocks.

The document lives in one of two places:

- a `.pjx` file, or
- the `template` string of the class that owns it.

It means the same thing in both. That sentence is the whole integration
between the three fronts: front 1 extends what `{#def#}` can say, front 2 adds
the other two blocks, front 3 adds the second place the document can live.
Nothing else is new.

When a class owns the document, the class declares the props and a `{#def#}`
block is redundant — already reported by the existing stale-header warning.

### Block grammar, stated once

```
block   := "{#" keyword whitespace body "#}"
keyword := "def" | "css" | "js"
```

- The keyword touches `{#`. `{# css tweaks #}` is prose and stays a comment.
- At most one block of each keyword per document; a second one is a
  `TemplateSyntaxError` naming the file and line.
- Blocks may appear in any order, anywhere in the document.
- All three are found by the same scanner, `template_blocks.find_block`.

Two silent failures in the grammar as first built are closed by this design:

- **A block before the header disabled the header.** `{#def#}` was matched
  only as the first thing in the file, so a `{#css#}` block above it turned a
  validated component into a prop-less one without a word. The header is now
  found wherever it sits, like the other blocks. (The legacy spaced form
  `{# def … #}` is still honoured, but only in first position, where it cannot
  be confused with prose.)
- **`#}` inside a body ended the block early.** Jinja closes a comment at the
  first `#}`, so a script containing that pair is cut there and its tail is
  rendered into the page as text. Jinja's lexing cannot be changed, but the
  result can be detected: once every comment is removed from a document, no
  `#}` should remain. If one does, registration raises a
  `TemplateSyntaxError` at its line, telling the author to break the pair up
  (`"#" + "}"`) or move the asset to a sibling file.

**Why there is no `{#python … #}` block.** It is the obvious fourth keyword
and it is exactly what ADR 0008 removed: code a type-checker cannot see,
loaded by an importer pyjinhx would have to own. The grammar stays closed at
three keywords, all of them declarative. The Python-hosted equivalent is the
same grammar turned inside out — instead of a Python block inside the
document, the document sits inside the Python: `template = """…"""`.

## Three shapes, and which to pick

**T — template only.** One `.pjx` file. No Python.

```jinja
{#def id: str, label: str, count: int = 0 #}
<span id="{{ id }}" class="badge">{{ label }} ({{ count }})</span>
{#css
.badge { border-radius: 999px; }
#}
```

**C — class in one file.** One `.py` file. The class holds the document.

```python
from pyjinhx import ReactiveComponent

from app.todos import Keys, store


def _plural(n: int) -> str:
    return "item" if n == 1 else "items"


class Counter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=store.remaining())

    @property
    def noun(self) -> str:
        return _plural(self.remaining)

    template = r"""
    <div class="counter">{{ remaining }} left</div>
    {#css
    .counter { font-weight: 600; }
    #}
    """
```

**S — split.** `.py` + `.pjx`, optionally `.css` / `.js`. What exists today,
unchanged and fully supported.

Picking one:

| If the component… | Shape |
|---|---|
| is props and markup — nothing computed in Python | **T** |
| needs Python: `load()`, a factory, a validator, a property, reactive keys, a subclass | **C** |
| needs Python *and* has a template long enough that you want full template tooling on it | **S** |
| has assets that are large, shared by subclasses with their own templates, or served in LINK mode | keep those assets as sibling files, in any shape |

The rule of thumb for docs: *start in T; move to C the day you need a
method; fall back to S when the string gets uncomfortable.* Moving between
shapes never changes the tag, the props or the rendered output, and a
codebase can mix all three per component.

Expected landing for the audited app: 91 classes → T, 183 → C (or stay S
where the template is big), sibling assets fold into blocks wherever they are
small and not inherited.

## Front 1 — the `{#def#}` header

The header keeps its shape: a Python parameter list, parsed with `ast`, never
executed. Five additions.

### 1a. A wider closed vocabulary

`_resolve_annotation` today knows `str int float bool list dict Any`, `Slot`,
`Children`, `T | None` and `Optional[T]`; everything else silently becomes
`Any` (a union such as `str | int` included). Added:

| Written | Becomes |
|---|---|
| `Literal["a", "b"]` | `typing.Literal["a", "b"]` (members must be literals) |
| `list[str]`, `dict[str, int]`, `list[Slot]` | the real generic, arguments resolved recursively |
| `str \| int` | the real union (today: `Any`) |
| `ExtraAttrs`, `AttrValue` | pyjinhx's own validated attribute types |

`Slot` and `Children` already work, including `Slot | None`. The 34
"blocked by Slot" classes are mostly component-typed fields
(`icon: AgentChip | None = None`); in a header that is written
`icon: Slot | None = None`, or with a dotted name (1c) when the precise type
matters.

### 1b. Mutable defaults need nothing

`items: list = []` and `attrs: ExtraAttrs = {}` are already safe: pydantic
copies a mutable default per instance, so the header form of
`Field(default_factory=list)` is just `= []`. This is documented and pinned by
a test; no code changes. It covers the bulk of the 32 `default_factory`
blockers and the 21 `ExtraAttrs` ones.

### 1c. Dotted names are import paths

A header cannot import, which is why constants, enums and factories block a
class from being dropped. One rule fixes all three without adding an import
statement to the grammar:

> In a header, a **dotted name** is resolved by importing it.

| Position | Written | Means |
|---|---|---|
| type | `when: datetime.datetime` | that type |
| type | `tone: app.ui.tones.Tone` | that enum / model / component class |
| default | `size: int = app.ui.constants.PAGE_SIZE` | that value, read once when the class is built |
| default | `at: datetime.datetime = datetime.datetime.now()` | `default_factory` — called per instance |

Resolution is `pkgutil.resolve_name` on the dotted text: a normal import of a
real module followed by attribute reads. Only `Name.Name…` chains are
accepted, and the only call form is a dotted name with empty parentheses;
anything else is the existing "must be a literal" error, extended to name the
two new forms. A bare, undotted unknown name stays an error for defaults and a
warning-then-`Any` for types, so a typo is never mistaken for an import.

This is the one place the design touches ADR 0008's "no exec" line, so
precisely: nothing from the template is compiled or executed. A declarative
reference causes Python to import a module the app already ships, lazily,
when the component is first built. It is the same thing a `.py` file's
`from … import …` does.

Expressions (`= PAGE_SIZE * 2`), lambdas and arguments to calls are out. A
component that needs those needs Python, and shape C is one file too.

### 1d. `auto_id` is spelled "`id` is required"

`auto_id = False` means exactly one thing: the caller must pass `id`. In a
header that is already expressible, with no new syntax:

```jinja
{#def id: str, title: str #}
```

Declaring `id` with no default builds the class with `auto_id = False`. `id`
with any other annotation or with a default is an error that says so.

### 1e. Header-only templates answer their tags

Today `<Note/>` resolves only if a class is registered for `note`; a
`note.pjx` with a `{#def#}` header and no class stays unregistered until some
Python calls `component("Note")`, and until then the tag passes through as
literal markup. That call is the last line of Python standing between a
header-only template and "no `.py` at all".

Design: **lazy, header-gated, on by default.**

- `build_registry` already walks every `.pjx` under `components_root`. It now
  also publishes the stems no class claimed, as `tag → path`. That is free:
  no file is opened.
- On a tag miss, the renderer asks the classless factory. If the tag has a
  recorded path, the factory reads that one file. A `{#def#}` header (an empty
  `{#def #}` counts) means "this is a component": the class is built and
  registered exactly as `component()` does today, under the same lock. No
  header means "this is just a template that happens to have a PascalCase
  name"; that answer is remembered and the tag passes through as before.
- Tags with no file at all — web components, typos — stay a single dict miss.
  No filesystem access is added to the miss path.

Cost: nothing at startup; one file read and one class build per tag, on first
use, then never again. Eager registration was rejected because it would parse
and build every orphan at import time, used or not.

Why the header is the opt-in: a behaviour change can then only reach a
template that *declared props* and whose tag is used but never resolved —
which today renders as a raw `<Note …/>` in the page, i.e. is already a bug.
A headerless orphan keeps today's behaviour exactly, and `component("X")`
still builds it on request.

Name clashes:

- **Class vs. template** — the class wins, silently; that is shape S.
- **Two orphan templates with one stem** — the first in the walk's sorted
  order wins, as `component()` already does, and a warning now names both
  paths (once per tag).
- **Template vs. inline-template class** (shape C class named like an orphan
  `.pjx`) — the class wins, same rule.

`component("X")` stays as the way to get the class object in Python.

## Front 2 — inline `{#css#}` / `{#js#}` blocks

As implemented on `feat/inline-css-js-blocks` (see
`docs/superpowers/specs/2026-11-25-inline-css-js-design.md` on that branch):
each block becomes an `InlineAsset`, a `Path` subclass named
`<template>#css`, appended to the descriptor's `css_paths` / `js_paths` after
any sibling file, so the whole existing asset pipeline handles it unchanged.
At most one block of each kind per document; LINK mode refuses an inline
asset.

What this design needs from it is one seam, described under "Reading a
document" below. Nothing about its behaviour for `.pjx` files changes.

## Front 3 — a class that carries its document

```python
class Chip(BaseComponent):
    label: str

    template = """
    <span class="chip">{{ label }}</span>
    """
```

Full detail, alternatives and rationale are in the candidates document; the
essentials:

- `template` is a string literal class attribute. `BaseComponent` declares
  `template: ClassVar[str | None] = None`, which is what makes the bare
  assignment legal for pydantic.
- It is an ordinary Python module, imported the ordinary way. Methods,
  classmethods, validators, reactive class keywords, module-level helpers and
  several components per module all work because nothing about the class
  changed — which is the point for the 183 classes that must stay classes.
- pyjinhx reads the string back from the module's source with `ast` (parse,
  never exec), lazily at first render, and again when the file's mtime
  changes — so a template edit is picked up without re-importing.
- The template MRO walk checks each ancestor's own `__dict__` for a
  `template` string before probing for a file. A subclass inherits a parent's
  inline template, or overrides it with its own string or its own `.pjx`.
- `ClassDescriptor.template_path` is the `.py` file;
  `ClassDescriptor.inline_class` names the owning class (`None` for a `.pjx`).
  Jinja is asked for `<path>::<ClassName>`.
- The extracted source is prefixed with a Jinja comment holding exactly
  enough newlines that template line *N* is line *N* of the `.py` file.
  Syntax errors, render tracebacks and block line numbers all point into the
  real file with no source map.

CSS and JS in shape C live **inside the template string**, as the same
`{#css#}` / `{#js#}` blocks. There are deliberately no `css = """…"""` /
`js = """…"""` class attributes: the string *is* the document, and a second
way to attach a stylesheet would be a second model. Sibling `chip.css` /
`chip.js` keep resolving through the unchanged MRO asset walk, so a shape C
component can keep large assets beside it.

Practical rules for the string: use `r"""` whenever it holds backslashes
(any non-trivial script does); use `'''` if the content holds `"""`.

## Reading a document — the one seam

With front 3, `template_path` may be a `.py` file, so
`template_path.read_text()` is no longer "the document". One function becomes
the only way to read one:

```python
# pyjinhx/sfc.py
def read_document(template_path: Path, inline_class: str | None) -> str
```

It returns the file's text for a `.pjx`, and `extract_template(...)` of it for
an inline class. Four callers, and no others, read template source:

| Caller | Today | Becomes |
|---|---|---|
| `AbsolutePathLoader.get_source` | `path.read_text()` | `read_document(path, inline_class)` |
| `template_blocks.inline_assets` | `template_path.read_text()` | same, taking `inline_class` |
| `InlineAsset.read_text` | `self.template.read_text()` | same; the asset carries `inline_class` |
| `props_header.template_has_props_header` | `template_path.read_text()` | same |

An inline class's asset is named `<path>::<ClassName>#css`, so two components
in one module each keep their own stylesheet and the pipeline's path-keyed
dedupe still works. Because of the line padding, "a second `{#css#}` block on
line 40" is line 40 of the `.py` file.

(Without this seam the block scanner, pointed at a `.py` file, would regex
the whole module: it would happen to work for one component per file and
raise a spurious "second block" error for two.)

## What does not change

- The tag → class registry and its collision rules for classes.
- Slots, children routing, strictness, auto-id generation, JSON coercion.
- Sibling `.css` / `.js` resolution and its MRO walk.
- ADR 0007's probe budget: the inline-template check is a dict lookup.
- The render cache key (`template_path` mtime — the `.py` file's for shape C,
  coarser than needed, never stale).
- Shape S. No deprecation is proposed.

## Migration tooling

`scripts/fold_components.py` — a repo script, not public API — with three
operations, each idempotent, each printing what it skipped and why:

- `assets <dir>`: fold a sibling `.css` / `.js` into a block in the template
  it sits beside. Skips an asset inherited by a subclass that has its own
  template, an asset containing `#}`, and a template that already has that
  block.
- `template <dir>`: fold a class's adjacent `.pjx` into
  `template = r"""…"""` as the last statement of the class (S → C). Skips
  content a raw triple-quoted string cannot hold.
- `declass <dir>`: for a class that is fields only and expressible in a
  header, write the `{#def#}` header and report the Python references that
  must change. It reports rather than rewrites imports.

## Open questions for the maintainer

1. **Dotted import paths in headers (1c).** The alternative is to keep
   headers import-free and send all 23 non-literal-default classes to shape
   C. Dotted paths are verbose but explicit, and keep "no Python needed"
   honest for constants and enums.
2. **Attribute name `template`.** Reserved class-level name on every
   component. No component in pyjinhx or in the audited app has a field by
   that name. Alternatives: `pjx_template`, `__template__`.
3. **Auto-registration switch.** Header-gated and lazy is proposed as the
   only behaviour. A `PjxSettings` flag to turn it off is cheap if wanted.
4. **LINK mode.** Inline assets are refused there. The audited app uses
   INLINE/NONE; is that true of every consumer that matters?
5. **Dev loop.** A template edit in shape C touches a `.py`, so `*.py`
   watchers restart the server where a `.pjx` edit would not.
6. **Escapes in non-raw strings.** `"\n"` in a non-raw `template` both
   changes the markup and shifts reported line numbers. Document only, warn,
   or require raw strings when a backslash is present?
7. **ADR 0008: supersede or amend?** Its literal decision — no
   `{# python #}` blocks, no exec at discovery — still holds in full.
8. **Specs and plans are gitignored** (`docs/superpowers/*` except
   `rebuild/`). These documents were force-added, as the inline-blocks spec
   was on its branch. Keep them in the PR or drop them before merge?
