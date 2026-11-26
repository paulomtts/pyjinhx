# ADR 0015: A pjx document may carry its class in a `{#python#}` block

**Status:** Accepted, 2026-11-26. Implemented; published, condensed, in `docs/decisions/0009`. Amends [ADR 0014](./0014-a-component-is-a-pjx-document.md); reverses the remaining part of [ADR 0008](./0008-drop-sfc-python-blocks.md).

## Context

ADR 0014 gave a component that needs a class one file by putting the template inside the Python module (`template = r"""…"""`). It kept ADR 0008's line: no Python inside a `.pjx`, no import hook, no stubs. Its reasoning was that Python tooling is the half that must not degrade.

That reasoning assumed the editor is a stock Python editor. The maintainer's editor is not: pjx-ls (the VS Code / Cursor extension) is meant to own the whole `.pjx` file the way Vue and Svelte tooling own theirs. It forwards the Python block to Pyright through a virtual document, handles the markup itself, and offers what neither half can alone: completing `{{ field }}` from the class's fields, checking a tag's props, jumping from a tag to its class, renaming across both. None of that is possible when the markup is a string inside a `.py` file.

The trial on the consumer app (`docs/superpowers/specs/2026-11-25-fewer-files-trial.md`) added two facts. Folding templates into `.py` files moved 52 long markup lines under the Python linter. And a header-only component has no importable class, while 88 of the 91 classes that could drop their `.py` are imported elsewhere.

## Options

1. **Keep ADR 0014 as it is.** One one-file shape for classes, hosted in `.py`.
2. **Replace it.** Host the class in the `.pjx` only, and remove the inline `template` string.
3. **Keep both.** Add a `{#python#}` block to the document grammar beside the `.py`-hosted shape.

For making the block importable: a `sys.meta_path` finder, a replaced path hook, or generated shadow `.py` files. Compared in `docs/superpowers/specs/2026-11-26-pjx-python-block-design.md`.

## Decision

Option 3, by maintainer decision. The model's sentence does not change: **a component is a pjx document, optionally owned by a Python class.** What changes is where that class may live.

1. **The grammar gains a fourth keyword.** `{#python` alone on a line opens the block; `#}` alone on a line closes it. It is an ordinary Jinja comment like the other three. At most one per document, never together with `{#def#}`.
2. **The block is a module.** `app/ui/card.pjx` is `app.ui.card`. A finder appended to `sys.meta_path`, installed when `pyjinhx` is imported, loads it. The body is compiled with the `.pjx` path as its filename and padded so its lines and columns are the file's.
3. **The markup belongs to the class named for the file** (`card.pjx` → `Card`), which is ADR 0007's rule and needs no new resolution code. Other classes and helpers may share the block.
4. **Discovery imports, it does not exec.** `setup()` imports every `{#python#}` document under `components_root` by its module name. A document the app already imported is not imported again.
5. **Type-checkers get stubs.** `python -m pyjinhx.stubgen` writes a line-preserving `card.pyi` beside each such `card.pjx`.
6. **A sibling `card.py` is refused**, at class creation, at startup and by `stubgen --check`.

### ADR 0008's objections, answered honestly this time

ADR 0014 answered them by not doing the thing. This ADR does the thing, so each objection is now a cost.

**"Requires extracting and exec-ing embedded Python at discovery time."** pyjinhx now owns a loader that compiles Python out of a template file. What is different from v0.x: it runs through Python's import protocol under the module's real name, once per process; discovery calls `importlib.import_module` and nothing else; a syntax error or a traceback names the `.pjx` line. ADR 0008's consequence "no exec of template-embedded Python anywhere in v2 discovery" no longer holds as written.

**"Couples template parsing to Python tooling — type-checking, LSP."** Yes. Type-checking a consumer of a `.pjx` class needs a generated stub, and checking the block's own body needs pjx-ls. This coupling is the feature: it is what lets one tool own both halves. A project that does not want it uses the `.py`-hosted shape.

**"Import semantics for code that lives in a non-`.py` file."** A finder sits on `sys.meta_path`. It is consulted only after every other finder has failed, so it cannot change how any existing module is found. `pkgutil.walk_packages` does not see `.pjx` modules, ruff does not lint them, and coverage cannot report on them.

**"A fourth shape … doesn't pay for itself."** There are now four shapes. The fourth pays in editor experience, for teams that use the editor it is built for.

### What it costs

- An import hook, installed as a side effect of `import pyjinhx`. The root package of an app that uses `.pjx` modules must import pyjinhx before the first of them.
- A generated file per component (`card.pyi`), normally git-ignored, and a generation step before type-checking in CI.
- `setup()` now imports application code, and reads each `.pjx` under `components_root` once to look for a block.
- An edit to a `{#python#}` block is not applied until the process restarts. pyjinhx warns when it sees one; it does not reload modules.
- Linting, formatting, coverage and CI type-checking of the block's body are partial or by extraction.
- A template is unmistakably trusted code: importing it runs it.

## Consequences

- New modules `pyjinhx/importer.py` (finder, loader, `import_document`), `pyjinhx/stubgen.py` and `pyjinhx/manifest.py`; `pyjinhx/sfc.py` gains the block scanner.
- pyjinhx is the single source of pjx-specific facts for editors: a parse-only `python -m pyjinhx.manifest` (components, props, block ranges, diagnostics; a workspace or one unsaved buffer), the block grammar as a versioned data file, and a conformance corpus both repositories run. None of them imports application code.
- `_walk_template`, `ClassDescriptor`, the Jinja loader's contract, `InlineAsset` and the render cache key are unchanged. `hide_block_lines` learns one keyword.
- ADR 0014's statements "nothing is exec-ed by pyjinhx", "no `sys.meta_path` finder is installed" and "the grammar stays closed at three keywords" are superseded by this ADR. Everything else in 0014 stands, including the `.py`-hosted shape.
- The public ADR `docs/decisions/0009` is revised to match before release.
- v0.x `{# python #}` files migrate by removing the space in the opener, provided they define a class named for the file.
- pjx-ls's `{# python #}` support (its PR #1) is updated to the v2 grammar in its own repository; see `docs/superpowers/specs/2026-11-26-pjx-ls-followup.md`.

## As built

Where the build differs from the design in `docs/superpowers/specs/2026-11-26-pjx-python-block-design.md`:

- A closer written `-#}` is refused, as Jinja would eat the line break after it. Text after the closer on its line is refused too.
- The finder sniffs a line that is only `{#python` or `{# python` in column 0 (`sfc.opener_line`), outside `{% raw %}` and tags. A prose comment such as `{# python helpers #}` is a plain template; an example in `<pre>` fails `setup()` unless indented or wrapped in `{% raw %}`.
- `setup()` does not import a plain `.py` subclass of a document's class; something must import it.
- `python -m app.ui.card` runs the block with the right `__file__`, but as `__main__`: the stem-class check does not run and the class is not registered.
- There is no `python -m pyjinhx.sfc` command. The docs show a short script over `sfc.python_source` for linting blocks with ruff.
- The manifest reports ranges (`start` and `end` positions) rather than bare `line` and `column`, absolute POSIX paths, and a few more fields; the reference page lists them.
- `python -m pyjinhx.stubgen --check` exits 1 for a stale, missing or orphaned stub or a document that needs a person, and 2 for a hand-written `.pyi` in a stub's way or a missing path.
- Pyright's `ignore` and `exclude` both silence a generated stub's diagnostics and still resolve imports through it (checked with basedpyright); the docs recommend `ignore`.
