# Block grammar conformance corpus

Each `<case>.pjx` is a document; `<case>.json` is what a scanner must report:

```json
{"blocks": [{"keyword": "css", "open_line": 2, "body_lines": [3, 3], "close_line": 4}],
 "error": null}
```

- Lines are 1-based and are the file's lines. `body_lines` is `[first, last]`,
  or `null` when there are no lines between the opener and the closer.
- `blocks` is in file order. When `error` is set, `blocks` is `[]`.
- `error` is `{"code", "line"}`: `second-block` (line of the second opener),
  `opener-not-at-line-start`, `python-block-early-close`, `text-after-closer`
  and `stray-comment-close` (line of the offending `#}`).
- Files are read as bytes: some cases use CRLF line endings.
