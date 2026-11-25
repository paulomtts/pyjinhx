# ADR 0009: A component is a pjx document, optionally owned by a class

**Status:** Accepted, 2026-11-25. Unreleased. Condensed from the rebuild ADR
0014 (`docs/superpowers/rebuild/adr/`), which supersedes the rebuild's ADR 0008
(drop `{# python #}` single-file components).

## Context

A component took up to four files: `.py`, `.pjx`, `.css`, `.js`. A consumer app
with 382 components showed the cost. Of its 275 classes, 91 existed only because
a `{#def#}` header could not express their fields, and 183 had to stay classes
(reactive keys, factories, properties, validators). It also carried 211 sibling
`.css` and 56 sibling `.js` files, many a few lines long.

v0.x had single-file components, a `{# python #}` block inside a `.pjx`. They were
dropped because they needed pyjinhx to extract and exec Python from a template
file, which broke type-checking, import semantics and tracebacks. That objection
is to a Python-in-template container. It does not apply to a template inside a
Python file.

## Decision

One model: **a component is a pjx document, optionally owned by a Python class.**
A document is markup plus up to three Jinja-comment blocks: `{#def#}` (props),
`{#css#}` and `{#js#}`. It lives in a `.pjx` file or in the `template` string
literal of its class, and means the same in both.

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

The grammar stays closed at three declarative keywords. There is no `{#python#}`
block.

Three shapes follow, none new: T (a `.pjx` alone), C (a `.py` holding its
template), S (`.py` + `.pjx`, optionally with sibling assets, unchanged). A
project can mix them per component, and `scripts/fold_components.py` makes the
mechanical moves.

## Consequences

- Nothing is exec-ed by pyjinhx and no import hook is installed. Python tooling
  sees an ordinary `.py` file.
- `template` is a reserved class attribute. A pydantic field of that name keeps
  its meaning.
- Markup in a Python string has no editor highlighting until an editor injection
  is installed, and a backslash needs a raw string.
- Editing a template in shape C edits a `.py` file, so reloaders that watch
  `*.py` restart where a `.pjx` edit would not.
- A header can trigger an import. A wrong dotted path fails when the component is
  first built, not at startup.
- A headed `.pjx` with no class used to pass its tag through as literal markup
  and now renders as a component.
- ADR 0007's on-disk convention (`.pjx`, snake_case) is extended, not broken:
  an inline template is consulted before the file probe.
- v0.x `{# python #}` files remain unsupported and still migrate by splitting.
