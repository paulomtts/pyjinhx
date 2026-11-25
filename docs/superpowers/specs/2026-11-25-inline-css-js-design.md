# Inline `{#css#}` / `{#js#}` blocks in `.pjx` templates

A template may carry its own stylesheet and script as single Jinja comments,
`{#css ... #}` and `{#js ... #}` (keyword glued to `{#`, so prose comments like
`{# css tweaks #}` stay comments), placed anywhere in the file after the `{#def#}`
header; being comments they are inert in plain Jinja and never reach the rendered
output. When the descriptor is built, each block found in the class's resolved
template becomes an `InlineAsset` — a `Path` subclass named `<template>#css` whose
`read_text()`/`read_bytes()` return the block body — appended to `css_paths` /
`js_paths`, so the existing pipeline (set dedupe, path-sorted order, builtin-first
split, `data-pjx-asset` tokens, the OOB delta, `all_assets()` bundles) treats it like
a sibling file without any new branch. A sibling file and a block of the same kind
are both shipped, sibling first (path sort puts `card.css` before `card.pjx#css`);
two blocks of one kind in one template raise `jinja2.TemplateSyntaxError` naming the
file and the second block's line, when the class is registered. LINK mode has no file
to point a URL at, so resolving an `InlineAsset` raises a `ValueError` naming the
template; use INLINE, or NONE with a bundle built from `all_assets()`. Block scanning
lives in `pyjinhx/template_blocks.py` as `find_block(source, keyword, filename)`, a
keyword-agnostic helper another block kind can reuse.
