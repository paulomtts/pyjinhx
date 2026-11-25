# block_grammar.json and the manifest

`block_grammar.json` is the grammar of `{#def`, `{#css`, `{#js` and
`{#python` blocks as data, for tools that scan `.pjx` files without Python.
`python -m pyjinhx.manifest --grammar` prints it; the same command with paths
prints the component manifest. `tests/fixtures/block_grammar/` holds a corpus
of documents with the result a scanner must give for each.

## Versions

`version` in this file is the grammar version, and the manifest reports it as
`grammar_version` next to its own `manifest_version`.

- Adding a field, a diagnostic code, a component kind or a keyword's optional
  rule does **not** change a version. Readers ignore what they do not know.
- Removing or renaming a field, or changing what a field or code means, does.

There is no JSON Schema file: the module docstring of `pyjinhx/manifest.py`
states the conventions (absolute POSIX paths, 1-based lines, 0-based UTF-16
columns, `{start, end}` ranges), and the tests pin the shape.
