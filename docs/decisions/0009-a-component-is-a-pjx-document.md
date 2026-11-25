# ADR 0009: A component is a pjx document, optionally owned by a class

**Status:** Accepted, 2026-11-25; revised 2026-11-26. Unreleased. Condensed from the
rebuild ADRs 0014 and 0015 (`docs/superpowers/rebuild/adr/`), which together supersede
the rebuild's ADR 0008 (drop `{# python #}` single-file components).

## Context

A component took up to four files: `.py`, `.pjx`, `.css`, `.js`. A consumer app
with 382 components showed the cost. Of its 275 classes, 91 existed only because
a `{#def#}` header could not express their fields, and 183 had to stay classes
(reactive keys, factories, properties, validators). It also carried 211 sibling
`.css` and 56 sibling `.js` files, many a few lines long.

v0.x had single-file components, a `{# python #}` block inside a `.pjx`. They were
dropped because they needed pyjinhx to extract and exec Python from a template
file, which broke type-checking, import semantics and tracebacks. A template
inside a Python file avoids all of that, and is offered. It also leaves the
markup as a string that no template tooling can read. An editor extension that
owns the whole `.pjx` file (pjx-ls, in the way Vue and Svelte tooling own theirs)
can do more than either half alone: complete `{{ field }}` from the class, check a
tag's props, rename across both. So the block returns, rebuilt on Python's import
protocol instead of an extractor, beside the Python-hosted form.

## Decision

One model: **a component is a pjx document, optionally owned by a Python class.**
A document is markup plus Jinja-comment blocks: `{#def#}` (props), `{#css#}`,
`{#js#}` and `{#python#}` (the owning class). It lives in a `.pjx` file or in the
`template` string literal of its class, and means the same in both.

1. **A class may hold its document.** The template walk checks each ancestor for
   an inline `template` before probing for a file. The string is recovered by
   parsing the module's source with `ast`, never by running it, so line N of the
   template is line N of the `.py` file.
2. **The `{#def#}` header says more.** `Literal`, generics, real unions,
   `ExtraAttrs` and `AttrValue`; a required `id: str` turns `auto_id` off; a
   dotted name is an import path for a type, a constant default, or with `()` a
   default factory. Paths resolve with `pkgutil.resolve_name` when the class is
   built. The header is never `eval`'d, but a template is trusted code: a
   dotted name imports its module and `pkg.f()` calls `f` per instance.
3. **A header-only template answers its tag.** Discovery records `.pjx` files no
   class claimed; on a tag miss, one that carries a header is built into a class.
   Lazy, header-gated, no `component()` call needed.
4. **Inline `{#css#}` / `{#js#}` blocks** ship through the existing asset
   pipeline, sibling file first. Template source is read through one function,
   `read_document`, never `template_path.read_text()`.
5. **A `.pjx` may hold its class.** `{#python` alone on a line opens a block that
   is the module `app.ui.card` for `app/ui/card.pjx`; `#}` alone on a line closes
   it. A finder appended to `sys.meta_path` when `pyjinhx` is imported loads it,
   compiled so its lines and columns are the file's. The markup belongs to the
   class named for the file. `setup()` imports every such document under
   `components_root`, and `python -m pyjinhx.stubgen` writes a `.pyi` beside each
   so type-checkers see the class. A block never comes with a `{#def#}` header,
   and never beside a `card.py` that defines the class.

The grammar is closed at these four keywords.

Four shapes follow: T (a `.pjx` alone), P (a `.pjx` holding its class), C (a `.py`
holding its template), S (`.py` + `.pjx`, optionally with sibling assets,
unchanged). A project can mix shapes per component, and
`scripts/fold_components.py` makes the mechanical moves.

### Which shape to pick

P and C are the same component written two ways, and each gives up something
different. P gives the markup full editor support and costs setup: an import
hook, generated stubs, partial ruff and coverage. C works with every stock Python
tool and leaves the markup as a string.

- Use **T** when the component is props and markup.
- Use **P** if your team edits with pjx-ls and accepts the setup.
- Use **C** if you want every Python tool to work with no setup.
- Use **S** when the template is long enough to want template tooling on its own,
  or assets are shared.

The guide has the comparison table.

## Consequences

- In shapes T, C and S nothing is exec-ed by pyjinhx and Python tooling sees
  ordinary `.py` files. Shape P adds an import hook, installed by `import pyjinhx`
  and consulted only for names nothing else found. The root package of an app
  that uses it must import pyjinhx before the first `.pjx` module. Importing a
  `.pjx` runs its block, so a template is trusted code in the plainest sense.
- Shape P needs generated stubs for type-checking, normally git-ignored, with
  Pyright's `reportMissingModuleSource` off. `setup()` imports application code.
  An edited block applies on restart; pyjinhx warns when it sees one and does not
  reload modules. Linting, formatting and coverage of a block are partial or by
  extraction, and `pkgutil` does not list `.pjx` modules.
- pyjinhx is the source of pjx facts for editors: `python -m pyjinhx.manifest`, a
  versioned grammar file and a conformance corpus, none of which imports
  application code.
- `template` is a reserved class attribute. A pydantic field of that name keeps
  its meaning.
- Markup in a Python string (shape C) has no editor highlighting until an
  injection is installed, and a backslash needs a raw string.
- Editing a template in shape C edits a `.py` file, so reloaders that watch
  `*.py` restart where a `.pjx` edit would not.
- A header can trigger an import. A wrong dotted path fails when the component is
  first built, not at startup.
- A headed `.pjx` with no class used to pass its tag through as literal markup
  and now renders as a component.
- A line that is only `{#python` in column 0 in any `.pjx` now makes it a document,
  so an example written that way must be indented or wrapped in `{% raw %}`. Prose
  such as `{# python helpers #}` stays a comment.
- ADR 0007's on-disk convention (`.pjx`, snake_case) is extended, not broken:
  an inline template is consulted before the file probe.
- v0.x `{# python #}` files migrate by removing the space in the opener,
  provided the class is named for the file.
