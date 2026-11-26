# pjx-ls follow-up for the `{#python#}` block

Status: a work list for a later change in the separate pjx-ls repository. Nothing here is part of the pyjinhx PR.
Design it depends on: `2026-11-26-pjx-python-block-design.md`, section "Facts
for editors".

## Where pjx-ls is today

- `master` is a TextMate grammar plus a formatter. It has no language
  forwarding and no knowledge of components.
- The branch `feat/language-server` (its PR #1, closed unmerged) targeted the
  v0.x block. Three things in it must not come back as they were:
  - its opener is `{# python` with a space, first line only. The v2 opener is
    `{#python`, column 0, anywhere;
  - it wrote a mirror `_pjx_virtual_<stem>.py` beside every `.pjx` so Pylance
    would analyse it. In v2 that file is importable application code: an
    app-side `rglob("*.py")` registry (the consumer app has one) would import
    it, define a second class for the tag, and trip pyjinhx's "two classes
    claim one document" refusal;
  - it appended to the user's `.gitignore`.

## The division of labour

pjx-ls forwards and adds a thin pjx-only layer. It does not re-derive pjx
facts. pyjinhx provides, all parse-only:

| Need | From pyjinhx |
|---|---|
| Which components exist, their tags, kinds, files | `python -m pyjinhx.manifest <root>` |
| A class's props: name, annotation as written, required, default, literal values, slot flags, positions | manifest `props` |
| Properties and methods, for `{{ … }}` | manifest `members` |
| Block line ranges | manifest `blocks`, or its own scanner checked against the corpus |
| Diagnostics pyjinhx would raise | manifest `diagnostics`; for an unsaved buffer, `--stdin --filename` |
| The block grammar | `python -m pyjinhx.manifest --grammar` (versioned) |
| Proof its scanner agrees | the corpus at `tests/fixtures/block_grammar/`, vendored at a pyjinhx tag |
| How a type-checker sees a `.pjx` class | the adjacent `card.pyi` from `python -m pyjinhx.stubgen` |
| The `template = …` forms of the `.py`-hosted shape | the commands reference page; the literal's span is in the manifest |

## Work list

1. **Grammar.** Recognise `{#python` per the grammar file: keyword touching
   `{#`, ending its line, opener in column 0, closer `#}` alone on its line.
   Scope the body as `source.python`. `{#-def` and friends are not blocks.
   Offer a quick-fix on the v0.x `{# python` opener.
2. **Scanner conformance.** Vendor the corpus and run the TypeScript scanner
   over it in CI. Read `grammar_version` from the manifest and warn when the
   installed pyjinhx speaks a newer one.
3. **Python forwarding without mirror files in the source tree.** The virtual
   Python document is the file with every non-block line blanked, which is
   exactly `python -m pyjinhx.sfc <file>`'s output and maps by identity
   (same line, same column). Where it lives is pjx-ls's design problem; the
   constraint from pyjinhx is only that no `.py` file appears inside an
   importable package. Imports *of* `.pjx` classes from that virtual document
   and from ordinary `.py` files resolve through the adjacent `.pyi` stubs, so
   nothing else has to be faked.
4. **Stubs on save.** Run `python -m pyjinhx.stubgen <workspace or file's
   package>` with the project interpreter after a `.pjx` with a block is
   saved (trust-gated, as before). Do not edit `.gitignore`; show the
   suggested pattern once if the stub is not ignored.
5. **Definition redirect.** A go-to-definition result that lands in a file
   carrying the stubgen marker is rewritten to the same line of the sibling
   `.pjx`. Stubs are line-preserving for this purpose.
6. **Cross-section features**, all driven by the manifest:
   - complete and hover `{{ name }}` from the document class's `props` and
     `members` (follow `bases` through other manifest entries for inherited
     ones; fall back to Pyright on the virtual document where the manifest's
     static mode stops);
   - validate a `<Tag …/>`'s attributes against that tag's `props`: unknown
     prop, missing required prop, value outside `literal_values`;
   - go to definition from a tag to `class.path` / `class.line`;
   - rename a prop across the block, the markup, and tags that pass it.
7. **Diagnostics.** Surface the manifest's `diagnostics` array as is, using
   the stdin mode for unsaved buffers. Do not re-implement the checks.
8. **Formatting.** Leave the block's body to ruff (`ruff format -` on the
   body, written back in place); keep the block where the author put it;
   never indent it.
9. **Debugging.** Contribute breakpoints for the pjx language so a
   breakpoint can be set in a block. Line numbers already match.
10. **The `.py`-hosted shape.** An injection grammar for
    `template = r"""…"""` matching the documented forms, using the manifest's
    literal span when it is available.

## Things pjx-ls may ask pyjinhx for later

Not built now; noted so the manifest's schema leaves room:

- an importing mode for the manifest (`--import`) that adds inherited fields
  and subclasses whose template is inherited;
- a command-line formatter for blocks, if format-on-save is not enough;
- a coverage.py plugin for `.pjx` files.
