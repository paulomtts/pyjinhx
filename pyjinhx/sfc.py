"""Split a single-file component (`.pjx`) into its `{# python #}` block and template.

A single-file component declares its Python class in a leading block::

    {# python
    class Counter(BaseComponent):
        remaining: int
    #}
    <div>{{ remaining }} left</div>

This module is the one canonical place that knows where the block ends; the
import hook, the stub generator, and validation all call ``split_pjx``.
"""
import re

_OPEN_RE = re.compile(r"^\s*\{#\s*python\b(?P<rest>.*)$")


def split_pjx(source: str) -> "tuple[str | None, str]":
    """Return ``(python_src, template_src)`` for a `.pjx` source string.

    ``python_src`` is ``None`` when there is no ``{# python #}`` block. When
    present it is left-padded with newlines so its line numbers match the
    original file. The block opens with ``{# python`` (alone on the first
    non-whitespace line) and closes at the first later line whose only
    non-whitespace content is ``#}`` — so inline ``#}`` inside Python is safe.
    """
    lines = source.splitlines(keepends=True)

    open_index = 0
    while open_index < len(lines) and lines[open_index].strip() == "":
        open_index += 1
    if open_index >= len(lines):
        return None, source

    match = _OPEN_RE.match(lines[open_index])
    if match is None:
        return None, source
    if match.group("rest").strip():
        raise ValueError("`{# python` opener must be alone on its line")

    close_index = None
    for index in range(open_index + 1, len(lines)):
        if lines[index].strip() == "#}":
            close_index = index
            break
    if close_index is None:
        raise ValueError("unterminated `{# python` block: no line containing only `#}`")

    padding = "\n" * (open_index + 1)
    python_src = padding + "".join(lines[open_index + 1 : close_index])
    template_src = "".join(lines[close_index + 1 :])
    return python_src, template_src
