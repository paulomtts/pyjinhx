# Block grammar conformance corpus

Each `<case>.pjx` is a document; `<case>.json` is what a scanner must report:

```json
{"blocks": [{"keyword": "css", "open_line": 2, "body_lines": [3, 3], "close_line": 4}],
 "error": null}
```

## Format

- Decode a `.pjx` as UTF-8 with a leading byte order mark stripped.
- Only `\n` and `\r\n` line endings are supported. Lines are 1-based and are
  the file's lines.
- `blocks` is in file order. `body_lines` is `[first, last]`, or `null` when
  no line lies between the opener and the closer. `def` blocks have no
  `body_lines`: a header is one expression, not a body.
- `error` is `{"code", "line"}`. When it is set, `blocks` is `[]`. When
  several errors are possible, the one on the lowest line wins.
- The corpus covers the scanners only. Refusals that need a class or a
  component (a `python` block next to a `{#def#}` header, a document with no
  markup) are not in it.
- Columns: Python's `ast` `col_offset` counts UTF-8 bytes, while a
  `SyntaxError.offset` counts characters. Both are the file's own columns,
  because the body is never dedented.

## Known gaps

A case with a `known_gap` key records what Jinja itself would report, and
says where pyjinhx's scanner differs. Other implementations may follow either
side; pyjinhx's test expects to fail on it, so a fix is noticed.

- Braces are not balanced inside `{{ }}`. Jinja keeps reading while a `{`,
  `(` or `[` is open, so `{{ {1: {2: 3}} ~ "{#" }}` is one tag; the scanner
  ends it at the first `}}`.
- Only the default delimiters are read. Custom `*_start_string` /
  `*_end_string` values and line statement or line comment prefixes are
  unsupported.

## Rules the cases pin down

- Comments follow Jinja's lexer: `{#`/`#}` inside a `{% raw %}` region or a
  `{{ }}` / `{% %}` tag (string literals included) are not comments.
- `css` and `js` must end their line; their `{#` may be indented. An empty
  css/js block is omitted from `blocks`; an empty python block is listed.
- A `python` opener must be in column 0 and its closer alone in column 0
  (trailing spaces and tabs allowed). `-#}` is not accepted as a closer, as
  Jinja would eat the line break after it.
- A stray `#}` (one left over once comments, tags and raw regions are
  removed) is an error only when the document has a non-empty css or js block,
  or a python block. Elsewhere `#}` is ordinary text.

## Error codes

| code | line |
|---|---|
| `second-block` | the second opener of a keyword. `find_block` detects it for def, css and js; `python_block` for python |
| `opener-not-at-line-start` | the `{#python` opener |
| `unclosed-block` | the `{#python` opener with no `#}` after it |
| `python-block-early-close` | the line of a `#}` that follows code |
| `closer-not-at-line-start` | the line of a closer that is indented or written `-#}` |
| `text-after-closer` | the line of the closer |
| `stray-comment-close` | the line of the leftover `#}` |
