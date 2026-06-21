"""Doc-lint: builtin examples in docs/ and the gallery test apps must only use
real component fields.

Catches stale documentation — e.g. ``PJXCard(title=...)`` after ``title`` was
removed in the composable-parts refactor. Builtins use ``extra="allow"``, so a
removed field silently becomes an HTML attribute at runtime; nothing raises, and
neither the gallery-demo test (which only validates ``<!-- demo: -->`` markers)
nor the integration/reactivity apps (which render but assert nothing on the
content) can see it. This test parses every ``PJXFoo(...)`` Python call and
``<PJXFoo ...>`` tag in the published docs **and** the two gallery test apps
(``tests/integration/app.py``, ``tests/reactivity/app.py`` — the builtin-usage
surfaces outside ``docs/`` that silently absorb stale fields) and asserts each
bare-word keyword/attribute is a declared field on that builtin.

Intentional HTML pass-through attrs are skipped: anything hyphenated (``data-*``,
``hx-*``, ``aria-*``) and the small set of bare-word global HTML attributes in
``HTML_GLOBALS`` below. If a real builtin field ever collides with one of those
names, the collision is documented inline.
"""
import re
from pathlib import Path

import pyjinhx.builtins as b
from pyjinhx.base import BaseComponent

_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _ROOT / "docs"

# Builtin classes keyed by their tag/class name.
_BUILTINS: dict[str, type] = {
    name: getattr(b, name)
    for name in b.__all__
    if isinstance(getattr(b, name), type) and issubclass(getattr(b, name), BaseComponent)
}

# Bare-word HTML attributes that legitimately pass through to a builtin's root
# as extras (they are not component fields). Hyphenated attrs are always skipped
# separately. Deliberately excludes ``title``/``body``/etc. so a stale field
# reference is still caught.
HTML_GLOBALS = {
    "role",
    "style",
    "tabindex",
    "lang",
    "dir",
    "hidden",
    "slot",
    "part",
    "popover",
    "inert",
    "draggable",
    "spellcheck",
    "translate",
    "contenteditable",
    "accesskey",
    "enterkeyhint",
    "autocapitalize",
    "onclick",
}

# Published documentation that carries builtin usage examples. The
# ``superpowers/`` tree is excluded: it holds gitignored local design specs and
# plans that intentionally show "before" (old-API) migration snippets.
_DOC_FILES = [
    p
    for p in sorted(_DOCS.rglob("*.md")) + sorted((_DOCS / "demos").rglob("*.py"))
    if "superpowers" not in p.parts
]

# The gallery test apps build real builtins but assert nothing on their rendered
# content, so a stale field there is the one non-doc surface that ``extra="allow"``
# silently swallows. Lint them too.
_DOC_FILES += [
    p
    for p in (
        _ROOT / "tests" / "integration" / "app.py",
        _ROOT / "tests" / "reactivity" / "app.py",
    )
    if p.exists()
]

_PY_CALL = re.compile(r"\b(PJX[A-Za-z0-9]+)\(")
_TAG_OPEN = re.compile(r"<(PJX[A-Za-z0-9]+)(?=[\s/>])")
_PY_KWARG = re.compile(r"([A-Za-z_]\w*)\s*=")


def _tag_attr_names(text: str, body_start: int) -> set[str]:
    """Attribute names of a ``<PJXFoo ...>`` open tag, starting just after the
    tag name. Quote-aware: an attribute value may contain a nested tag (e.g.
    ``start="<PJXIcon name='plus'/>"``), so ``>`` and ``=`` inside a quoted value
    are skipped rather than mistaken for the tag end or another attribute.
    """
    names: set[str] = set()
    i, n = body_start, len(text)
    while i < n:
        c = text[i]
        if c == ">":
            break
        if c.isspace() or c == "/":
            i += 1
            continue
        # read an attribute name
        start = i
        while i < n and (text[i].isalnum() or text[i] in "-_:"):
            i += 1
        name = text[start:i]
        # skip whitespace, then check for '='
        j = i
        while j < n and text[j].isspace():
            j += 1
        if j < n and text[j] == "=":
            j += 1
            while j < n and text[j].isspace():
                j += 1
            if j < n and text[j] in "\"'":  # quoted value — skip to matching quote
                quote = text[j]
                j += 1
                while j < n and text[j] != quote:
                    j += 1
                j += 1
            else:  # unquoted value — to next whitespace or '>'
                while j < n and not text[j].isspace() and text[j] != ">":
                    j += 1
            if name:
                names.add(name)
        i = j if j > i else i + 1
    return names


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _py_call_kwargs(text: str, open_paren_index: int) -> set[str]:
    """Top-level (depth-1) keyword names of a ``PJXFoo(...)`` call.

    Scans from the opening paren tracking depth so nested calls
    (``PJXCard(content=PJXCardHeader(title=...))``) contribute their kwargs to
    their own component, not the outer one.
    """
    depth = 0
    i = open_paren_index
    n = len(text)
    segment_start = open_paren_index + 1
    names: set[str] = set()
    while i < n:
        c = text[i]
        if c == "(":
            depth += 1
            if depth == 1:
                segment_start = i + 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        elif c == "," and depth == 1:
            seg = text[segment_start:i]
            m = _PY_KWARG.match(seg.lstrip())
            if m:
                names.add(m.group(1))
            segment_start = i + 1
        i += 1
    # last segment before the closing paren
    if segment_start <= i:
        seg = text[segment_start:i]
        m = _PY_KWARG.match(seg.lstrip())
        if m:
            names.add(m.group(1))
    return names


def _collect_violations() -> list[str]:
    violations: list[str] = []
    for path in _DOC_FILES:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_ROOT)

        # Python-call form: PJXFoo(kwarg=...)
        for m in _PY_CALL.finditer(text):
            comp = m.group(1)
            cls = _BUILTINS.get(comp)
            if cls is None:
                continue
            for kw in _py_call_kwargs(text, m.end() - 1):
                if "-" in kw or kw in HTML_GLOBALS or kw in cls.model_fields:
                    continue
                violations.append(
                    f"{rel}:{_line_of(text, m.start())}: {comp}({kw}=...) — "
                    f"'{kw}' is not a field of {comp}"
                )

        # Tag form: <PJXFoo attr=...>
        for m in _TAG_OPEN.finditer(text):
            comp = m.group(1)
            cls = _BUILTINS.get(comp)
            if cls is None:
                continue
            for attr in _tag_attr_names(text, m.end()):
                if "-" in attr or ":" in attr or attr in HTML_GLOBALS or attr in cls.model_fields:
                    continue
                violations.append(
                    f"{rel}:{_line_of(text, m.start())}: <{comp} {attr}=...> — "
                    f"'{attr}' is not a field of {comp}"
                )
    return violations


def test_docs_examples_use_real_builtin_fields():
    violations = _collect_violations()
    assert not violations, (
        "Docs reference builtin keyword(s)/attribute(s) that are not declared "
        "fields (likely a removed/renamed field documented by mistake). Fix the "
        "example, or — if it is a deliberate HTML pass-through attribute — add the "
        "bare-word name to HTML_GLOBALS in this test.\n\n" + "\n".join(violations)
    )
