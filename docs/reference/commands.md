# Command line tools

Three modules run with `python -m` and read `.pjx` files without importing your
application: `pyjinhx.stubgen`, `pyjinhx.manifest` and, as a library, `pyjinhx.sfc`.
They parse; none of them runs a block, so they are safe on an untrusted or broken
workspace. They are for [shape P](../guide/components.md#shape-p-the-class-in-the-pjx)
and for editors. There is no console script: run them with your project's interpreter.

## `python -m pyjinhx.stubgen`

```text
python -m pyjinhx.stubgen [--check] [path ...]
```

Writes `card.pyi` beside every `card.pjx` that has a `{#python` block, under the given
files or directories (default: the current directory). The stub is the block's Python
with each function body replaced by `...`, except `__init__` bodies, which are kept.
Every class, `def` and field keeps its line in the `.pjx`. The opener's line holds the
marker `# pyjinhx.stubgen: generated from card.pjx; do not edit`.

- A stub is only ever overwritten or deleted if it carries the marker. A `.pyi` without
  it is hand-written and is left alone.
- A marked stub whose `.pjx` is gone, or has lost its block, is deleted.
- No stub is written for a block that a `card.py` or a `card/` directory shadows.
- Hidden directories, virtualenvs (any directory with a `pyvenv.cfg`), `site-packages`,
  `dist-packages`, `build`, `dist`, `__pycache__` and `node_modules` are skipped.
- A file only counts as a document if a line is only `{#python` in
  column 0, outside `{% raw %}`, as for the import hook.

With `--check` nothing is written. The command lists the stubs that are stale, missing or
orphaned, and the documents that need a person (shadowed, malformed, or a hand-written
`.pyi` in a stub's place), and fails.

| Exit code | Meaning |
|---|---|
| `0` | every stub is as it should be |
| `1` | with `--check`: a stub is stale, missing or orphaned; or something needs a person (a shadowed or malformed document) |
| `2` | a hand-written `.pyi` is in a stub's way, or a path does not exist |

Output is one line per finding, `path[:line[:column]]: what`. Without `--check`, what the
command fixed (`wrote`, `rewrote`, `removed`) goes to standard output and the rest to
standard error. See [Stubs and type checking](../guide/components.md#stubs-and-type-checking)
for the `.gitignore` and Pyright settings.

## `python -m pyjinhx.manifest`

```text
python -m pyjinhx.manifest [--sys-path DIR ...] [path ...]
python -m pyjinhx.manifest --stdin --filename FILE [--sys-path DIR ...]
python -m pyjinhx.manifest --grammar
```

Prints one JSON document describing every component under the paths, and pyjinhx's own
builtins. It exits 0 even when diagnostics are present, because they are data; it exits 2
for a path that does not exist.

- `--stdin --filename FILE` describes the text on standard input as the file `FILE`,
  which may be unsaved. It is the mode an editor calls on each change. The file's
  neighbours are read from disk, so an unsaved neighbour is not seen.
- `--sys-path DIR` (repeatable) names a directory modules are imported from, so
  `class.module` matches what Python would import. Without it, the module name is the
  path below the top of the package chain (the highest directory with an `__init__.py`).
- `--grammar` prints [the block grammar](#the-block-grammar) and exits.

### Conventions

- Paths are absolute and POSIX, so the output does not depend on where it ran.
- A position is `{"line", "column"}`. Lines are 1-based; columns are 0-based UTF-16 code
  units, which is what LSP uses. A range is `{"start", "end"}` of two positions.
- `annotation` and `default` are source text as written.

### Shape

```json
{
  "manifest_version": 1,
  "grammar_version": 1,
  "pyjinhx_version": "1.16.0",
  "roots": ["/work/app"],
  "components": [
    {
      "tag": "TodoCount",
      "name": "todo_count",
      "id": "/work/app/ui/todo_count.pjx#TodoCount",
      "kind": "pjx-python",
      "builtin": false,
      "document": {"path": "/work/app/ui/todo_count.pjx", "markup_lines": [11, 11]},
      "blocks": [
        {"keyword": "python", "open_line": 1, "body_lines": [2, 9], "close_line": 10},
        {"keyword": "css", "open_line": 12, "body_lines": [13, 13], "close_line": 14}
      ],
      "class": {
        "module": "app.ui.todo_count",
        "qualname": "TodoCount",
        "path": "/work/app/ui/todo_count.pjx",
        "range": {"start": {"line": 5, "column": 6}, "end": {"line": 5, "column": 15}},
        "bases": ["BaseComponent"],
        "stub": "/work/app/ui/todo_count.pyi"
      },
      "props": [
        {"name": "remaining", "annotation": "int", "required": false, "default": "0",
         "literal_values": null, "slot": false, "children": false,
         "range": {"start": {"line": 6, "column": 4}, "end": {"line": 6, "column": 13}}}
      ],
      "members": [
        {"name": "label", "kind": "method",
         "range": {"start": {"line": 8, "column": 8}, "end": {"line": 8, "column": 13}}}
      ],
      "assets": {"css": null, "js": null},
      "replaces": false,
      "strict": null,
      "has_stale_def_header": false
    }
  ],
  "diagnostics": [
    {"path": "/work/app/ui/card.pjx",
     "range": {"start": {"line": 9, "column": 0}, "end": {"line": 9, "column": 14}},
     "severity": "error", "code": "python-block-early-close", "message": "..."}
  ]
}
```

### Fields

| Field | Meaning |
|---|---|
| `manifest_version`, `grammar_version` | change when a field is removed or renamed, or its meaning changes. A field may be added without a bump, so ignore keys you do not know |
| `pyjinhx_version` | the installed version, or `"unknown"` |
| `roots` | the paths that were read |
| `tag`, `name` | the component's PascalCase tag and its snake_case file stem |
| `id` | `path#qualname` of the class, or the document path when there is no class |
| `kind` | `template` (T), `pjx-python` (P), `py-template` (C) or `split` (S) |
| `builtin` | true for components shipped in pyjinhx |
| `document` | `path` of the `.pjx`, or of the `.py` for kind `py-template`, and `markup_lines`, the first and last lines of the markup; for `py-template` it is the span of the string literal's contents |
| `blocks` | each `{#def`, `{#css`, `{#js` and `{#python` block in file order: `keyword`, `open_line`, `close_line` and `body_lines` (`[first, last]`, or `null` when empty). A `def` has no `body_lines` |
| `class` | `module` (or null if the file has no importable name), `qualname`, `path`, `range` of the class name, `bases` as written, and `stub`, the path of the generated `.pyi` or null. `null` for kind `template` |
| `props` | the declared fields, or for kind `template` the `{#def#}` header's arguments before any name in it is resolved. `literal_values` lists the members of a `Literal[...]` of literals; `slot` and `children` are true when the annotation names `Slot` or `Children` |
| `members` | properties, methods and classmethods (`kind`: `property`, `method`, `classmethod`), for `{{ ... }}` completion |
| `assets` | the sibling `.css` and `.js` paths, or null |
| `replaces` | the class says `pjx_replace=True` |
| `strict` | `true` or `false` when the class body sets `extra` in its `model_config`; null when it inherits the setting, which static reading cannot follow. `false` for kind `template` |
| `has_stale_def_header` | a hand-written class whose template still has a `{#def#}` header |

### Diagnostics

`diagnostics` lists what pyjinhx would refuse or warn about that can be seen without
importing. Each has `path`, `range`, `severity` (`error` or `warning`), `code` and
`message`. The codes:

| Code | Meaning |
|---|---|
| `python-block-early-close`, `second-block`, `text-after-closer`, `closer-not-at-line-start`, `unclosed-block`, `stray-comment-close` | a malformed block; see [the grammar](#the-block-grammar) |
| `python-syntax-error` | the block's Python does not parse |
| `def-with-python` | a `{#def#}` header and a `{#python` block in one document |
| `def-header-invalid` | a `{#def#}` header that is not a list of simple named props |
| `no-markup` | a document with a block and no markup |
| `no-component-class`, `ambiguous-component-class` | no class, or two, named for the file |
| `template-in-block` | a class in a block assigns `template` |
| `class-outside-document` | a `.py` class is named for a `.pjx` that holds a block, so the class would own a document that already belongs to the block's class |
| `shadowed-by-module` | a `card.py` or `card/` hides `card.pjx` |
| `no-module-name` | no import name can be derived for the file |
| `template-not-literal` | `template` is not one plain string literal |
| `stub-missing`, `stub-stale`, `stub-orphaned`, `stub-handwritten` | the state of the generated stub (warnings) |
| `tag-collision` | two components share a name and none says `pjx_replace=True` (warning) |
| `unreadable-file`, `internal-error` | the file could not be read, or the reader failed |

### What static mode cannot see

- A class is a component only if a `<snake>.pjx` sits beside its module or it assigns
  `template`. A subclass that inherits its template is not listed, and inherited fields
  are not in `props`; `bases` names where to look.
- Whether a class subclasses `BaseComponent`: a base is a name, and what it names needs an
  import.
- Classes nested in a function or another class.
- Tag collisions in `--stdin` mode are only checked among the buffer's neighbours and the
  builtins.

## The block grammar

`python -m pyjinhx.manifest --grammar` prints `pyjinhx/block_grammar.json`, the grammar of
`{#def`, `{#css`, `{#js` and `{#python` blocks as data, for tools that scan `.pjx` files
without Python. Its `version` is `grammar_version` in the manifest. It lists:

- the four keywords, and that the keyword touches `{#`;
- which keywords must end their line (`css`, `js`, `python`) and which take whitespace or
  nothing (`def`);
- the terminator, the first `#}`, as Jinja reads it;
- the extra `python` rules: opener in column 0, closer alone on its line in column 0, at
  most one per document, not together with `def`;
- the legacy spaced `{# def` header, honoured as the first thing in a document;
- the error codes above.

`{#-def`, `{#- css` and any other whitespace-control form is not a block, and neither is
`{# python`. The Python scanner is not driven by this file; a test runs both
over the corpus to prove they agree.

The conformance corpus is `tests/fixtures/block_grammar/` in the repository: small `.pjx`
sources, each with a JSON file beside it holding the blocks a scanner must report (with
their line ranges) or the error code and line. An editor extension can vendor the
directory at a pyjinhx tag and run its own scanner over it. Its README lists the known
gaps (braces inside `{{ }}` are not balanced, and only the default Jinja delimiters are
read).

## `pyjinhx.sfc`

`pyjinhx.sfc` is the stdlib-only module the others share. It is not part of the public
API, but two of its jobs are worth knowing:

- `python_source(text, filename)` returns a block's Python padded so that line N of the
  code is line N of the file (see the ruff loop under
  [Known limits](../guide/components.md#known-limits-of-shape-p)).
- It reads the `.py`-hosted form, shape C, from the module's source without running it.
  A template is recognised only inside a class body, as `template = <literal>` or
  `template: <annotation> = <literal>`, where the literal is one string token: `"..."`,
  `'...'`, `"""..."""` or `'''...'''`, with an optional `r` or `R` prefix. Not an
  f-string, not adjacent literals, not a name or a call. The last assignment in the body
  wins. An editor grammar that matches the same set degrades to no highlighting, never to
  a wrong diagnostic.
