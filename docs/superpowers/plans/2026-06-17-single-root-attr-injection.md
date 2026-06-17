# Single-root invariant + universal attribute injection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make inline tag attributes (`hx-*`, `data-*`, `aria-*`, …) pass through onto the root element of *every* component automatically, and enforce a React-style "exactly one root element per template" invariant for all components.

**Architecture:** After a component's template renders to its own HTML subtree (in `renderer.render_component_with_context`, before page-level assets are appended), validate it has exactly one top-level element and splice the component's collected extra attributes into that root element's opening tag. This replaces the old `pyjinhx.builtins`-gated `extra_attrs_html` context variable and the hand-placed `{{ extra_attrs_html }}` template token.

**Tech Stack:** Python 3, Pydantic v2, Jinja2, `html.parser.HTMLParser`, pytest.

## Global Constraints

- Inline attribute collisions use **override** semantics: a colliding attribute (including `class`/`style`) is fully replaced by the inline value; non-colliding inline attrs are appended.
- Every component template must render **exactly one** top-level element. 0 (text-only) or 2+ siblings raise `ValueError`. Whitespace and comments around the root are ignored.
- Attribute names must match the existing `_ATTR_NAME_RE = re.compile(r"[A-Za-z@:][A-Za-z0-9_.:@-]*")`.
- An attribute value containing both `"` and `'` raises `ValueError` (message contains the word `both`). A value with one quote type is emitted with the other quote.
- No backward-compatibility shim for multi-root templates — they are expected to be fixed.
- Run tests with `uv run pytest` from the repo root.

---

### Task 1: `collect_extra_attrs` — return the merged attr dict (refactor `render_extra_attrs`)

**Files:**
- Modify: `pyjinhx/base.py:59-84` (replace `render_extra_attrs` with `collect_extra_attrs`)
- Test: `tests/unit/test_root_attr_injection.py` (new)

**Interfaces:**
- Produces: `collect_extra_attrs(component) -> dict[str, str]` — ordered dict; `extra_attrs` field entries first, then stray `model_extra` string entries with valid attribute names (existing entries win via `setdefault`). Does **not** serialize and does **not** raise on quote content (serialization/quoting moves to Task 2).

- [ ] **Step 1: Find all callers of `render_extra_attrs`**

Run: `grep -rn "render_extra_attrs" pyjinhx tests`
Expected: the definition at `pyjinhx/base.py:59`, the context-var assignment at `pyjinhx/base.py:367`, and possibly builtin `@property` callers. Note every hit — Task 3 removes the line 367 caller; any builtin `@property` caller must be updated to use `collect_extra_attrs` + the Task 2 serializer, or deleted if now unused. If a caller exists that this plan does not otherwise touch, update it in this task to call `collect_extra_attrs` and serialize via the Task 2 `serialize_attr` helper.

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_root_attr_injection.py
from pyjinhx.base import collect_extra_attrs
from pyjinhx.builtins import PJXPopoverTrigger


def test_collect_merges_extra_attrs_field_and_stray_attrs():
    component = PJXPopoverTrigger(
        id="t",
        content="go",
        extra_attrs={"data-explicit": "1"},
        **{"data-stray": "2", "title": "hi"},
    )
    result = collect_extra_attrs(component)
    assert result == {"data-explicit": "1", "data-stray": "2", "title": "hi"}


def test_collect_skips_children_field_and_non_string_extras():
    component = PJXPopoverTrigger(id="t", content="go")
    result = collect_extra_attrs(component)
    # the children field ("content") must not leak into attrs
    assert "content" not in result
    assert result == {}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_root_attr_injection.py -v`
Expected: FAIL — `ImportError: cannot import name 'collect_extra_attrs'`.

- [ ] **Step 4: Replace `render_extra_attrs` with `collect_extra_attrs`**

In `pyjinhx/base.py`, replace the whole `render_extra_attrs` function (lines 59-84) with:

```python
def collect_extra_attrs(component: "BaseComponent") -> dict[str, str]:
    """Collect a component's pass-through HTML attributes as an ordered dict.

    Merges the ``extra_attrs`` dict with stray tag attributes (pydantic extras
    that are plain strings with valid attribute names). Serialization and quote
    handling happen at injection time (see ``pyjinhx.root_attrs``).
    """
    attrs = dict(getattr(component, "extra_attrs", None) or {})
    children_field = type(component)._pjx_children_field
    for name, value in (component.model_extra or {}).items():
        if name == children_field or not isinstance(value, str):
            continue
        if _ATTR_NAME_RE.fullmatch(name):
            attrs.setdefault(name, value)
    return attrs
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_root_attr_injection.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add pyjinhx/base.py tests/unit/test_root_attr_injection.py
git commit -m "refactor: collect_extra_attrs returns dict (replaces render_extra_attrs)"
```

---

### Task 2: `pyjinhx/root_attrs.py` — single-root validation + attribute injection

**Files:**
- Create: `pyjinhx/root_attrs.py`
- Test: `tests/unit/test_root_attrs_module.py` (new)

**Interfaces:**
- Consumes: nothing from other tasks (stdlib only — no imports from `base`/`renderer`, to avoid an import cycle).
- Produces:
  - `serialize_attr(name: str, value: str) -> str` — returns `'name="value"'` or `"name='value'"`; raises `ValueError` (message contains `both`) if the value has both quote types.
  - `find_single_root(html: str, *, component_name: str) -> tuple[int, int]` — `(start, end)` char span of the root opening tag; raises `ValueError` unless there is exactly one top-level element.
  - `apply_root_attrs(html: str, *, component_name: str, attrs: dict[str, str]) -> str` — always validates single root; if `attrs` is non-empty, applies override-semantics injection into the root opening tag and returns the new HTML; otherwise returns `html` unchanged.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_root_attrs_module.py
import pytest

from pyjinhx.root_attrs import apply_root_attrs, find_single_root, serialize_attr


def test_serialize_attr_prefers_double_quotes():
    assert serialize_attr("data-x", "y") == 'data-x="y"'


def test_serialize_attr_falls_back_to_single_quotes():
    assert serialize_attr("hx-headers", '{"a": "b"}') == "hx-headers='{\"a\": \"b\"}'"


def test_serialize_attr_both_quote_types_raises():
    with pytest.raises(ValueError, match="both"):
        serialize_attr("data-x", "a\"b'c")


def test_find_single_root_returns_span_of_opening_tag():
    html = "  <article class=\"c\">body</article>"
    start, end = find_single_root(html, component_name="X")
    assert html[start:end] == '<article class="c">'


def test_find_single_root_ignores_leading_comment_and_whitespace():
    html = "<!-- hi -->\n<div>x</div>"
    start, end = find_single_root(html, component_name="X")
    assert html[start:end] == "<div>"


def test_find_single_root_allows_void_root():
    html = '<input type="text">'
    start, end = find_single_root(html, component_name="X")
    assert html[start:end] == '<input type="text">'


def test_find_single_root_allows_self_closing_root():
    start, end = find_single_root("<br/>", component_name="X")
    assert (start, end) == (0, 5)


def test_find_single_root_rejects_two_top_level_elements():
    with pytest.raises(ValueError, match="exactly one root"):
        find_single_root("<div>a</div><div>b</div>", component_name="Widget")


def test_find_single_root_rejects_zero_elements():
    with pytest.raises(ValueError, match="exactly one root"):
        find_single_root("just text", component_name="Widget")


def test_apply_root_attrs_appends_non_colliding_attr():
    html = '<article class="c">x</article>'
    out = apply_root_attrs(html, component_name="X", attrs={"data-y": "1"})
    assert out == '<article class="c" data-y="1">x</article>'


def test_apply_root_attrs_overrides_colliding_attr():
    html = '<article class="card">x</article>'
    out = apply_root_attrs(html, component_name="X", attrs={"class": "mt-4"})
    assert out == '<article class="mt-4">x</article>'


def test_apply_root_attrs_injects_into_void_root():
    html = '<input type="text">'
    out = apply_root_attrs(html, component_name="X", attrs={"data-y": "1"})
    assert out == '<input type="text" data-y="1">'


def test_apply_root_attrs_injects_before_self_closing_slash():
    html = "<br/>"
    out = apply_root_attrs(html, component_name="X", attrs={"data-y": "1"})
    assert out == '<br data-y="1"/>'


def test_apply_root_attrs_empty_attrs_still_validates():
    with pytest.raises(ValueError, match="exactly one root"):
        apply_root_attrs("<div></div><div></div>", component_name="X", attrs={})


def test_apply_root_attrs_empty_attrs_returns_unchanged():
    html = "<div>x</div>"
    assert apply_root_attrs(html, component_name="X", attrs={}) == html
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_root_attrs_module.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pyjinhx.root_attrs'`.

- [ ] **Step 3: Create `pyjinhx/root_attrs.py`**

```python
"""Single-root validation and inline attribute injection for components.

A component's rendered template must contain exactly one top-level element
(React-style). Inline tag attributes collected from the component are spliced
into that root element's opening tag with override semantics.

This module is stdlib-only on purpose: it must not import ``base`` or
``renderer`` (both import each other), so it stays free of the cycle.
"""

import re
from html.parser import HTMLParser

# HTML void elements have no closing tag, so they never open a nesting level.
_VOID_ELEMENTS = frozenset(
    {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
)


def serialize_attr(name: str, value: str) -> str:
    """Emit ``name="value"``; fall back to single quotes when the value has ``"``."""
    if '"' in value:
        if "'" in value:
            raise ValueError(
                f"attribute {name!r} value must not contain both '\"' and \"'\""
            )
        return f"{name}='{value}'"
    return f'{name}="{value}"'


class _RootScanner(HTMLParser):
    """Counts top-level elements and records the first root's opening-tag span."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._depth = 0
        self.root_count = 0
        self.root_start: int | None = None
        self.root_tag_text: str | None = None
        self._line_offsets: list[int] = [0]

    def feed(self, data: str) -> None:
        # Map (line, col) from getpos() to absolute string offsets.
        offset = 0
        self._line_offsets = [0]
        for line in data.splitlines(keepends=True):
            offset += len(line)
            self._line_offsets.append(offset)
        super().feed(data)

    def _abs_offset(self) -> int:
        line, col = self.getpos()
        return self._line_offsets[line - 1] + col

    def _record_top_level(self) -> None:
        if self._depth == 0:
            self.root_count += 1
            if self.root_count == 1:
                self.root_start = self._abs_offset()
                self.root_tag_text = self.get_starttag_text()

    def handle_starttag(self, tag, attrs):
        self._record_top_level()
        if tag.lower() not in _VOID_ELEMENTS:
            self._depth += 1

    def handle_startendtag(self, tag, attrs):  # <tag/> — self-contained
        self._record_top_level()

    def handle_endtag(self, tag):
        if self._depth > 0:
            self._depth -= 1


def find_single_root(html: str, *, component_name: str) -> tuple[int, int]:
    """Return the (start, end) char span of the sole root element's opening tag.

    Raises ``ValueError`` unless ``html`` has exactly one top-level element.
    """
    scanner = _RootScanner()
    scanner.feed(html)
    scanner.close()
    if scanner.root_count != 1 or scanner.root_start is None or scanner.root_tag_text is None:
        raise ValueError(
            f"<{component_name}> template must render exactly one root element "
            f"(found {scanner.root_count})"
        )
    start = scanner.root_start
    return start, start + len(scanner.root_tag_text)


def _override_tag(tag_text: str, attrs: dict[str, str]) -> str:
    """Apply ``attrs`` onto a single opening-tag string with override semantics."""
    body = tag_text
    for name, value in attrs.items():
        pair = serialize_attr(name, value)
        pattern = re.compile(
            r"\s" + re.escape(name) + r"\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s/>]*)"
        )
        if pattern.search(body):
            body = pattern.sub(" " + pair, body, count=1)
        elif body.rstrip().endswith("/>"):
            idx = body.rindex("/>")
            body = body[:idx] + pair + " " + body[idx:]
        else:
            idx = body.rindex(">")
            body = body[:idx] + " " + pair + body[idx:]
    return body


def apply_root_attrs(html: str, *, component_name: str, attrs: dict[str, str]) -> str:
    """Validate the single-root invariant and inject ``attrs`` into the root tag."""
    start, end = find_single_root(html, component_name=component_name)
    if not attrs:
        return html
    new_tag = _override_tag(html[start:end], attrs)
    return html[:start] + new_tag + html[end:]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_root_attrs_module.py -v`
Expected: PASS (all tests). If `test_apply_root_attrs_injects_before_self_closing_slash` fails on spacing, adjust `_override_tag`'s `/>` branch so the result is exactly `<br data-y="1"/>`.

- [ ] **Step 5: Commit**

```bash
git add pyjinhx/root_attrs.py tests/unit/test_root_attrs_module.py
git commit -m "feat: root_attrs module — single-root validation + attr injection"
```

---

### Task 3: Wire injection into the renderer; remove the builtin gate + context var

**Files:**
- Modify: `pyjinhx/renderer.py:300-303` (inject after `stamp_reactive_markup`, before the `emit_assets` branch)
- Modify: `pyjinhx/base.py:366-367` (delete the `pyjinhx.builtins` gate + `extra_attrs_html` assignment)
- Test: `tests/unit/test_root_attr_injection.py` (extend)

**Interfaces:**
- Consumes: `collect_extra_attrs` (Task 1), `apply_root_attrs` (Task 2).
- Produces: every component render now emits collected inline attrs on its root and enforces the single-root invariant.

- [ ] **Step 1: Write the failing tests (app component parity + override + invariant)**

```python
# append to tests/unit/test_root_attr_injection.py
import pytest

from pyjinhx import BaseComponent, Renderer


def _write(tmp_path, name, template):
    path = tmp_path / name
    path.write_text(template)
    return path


def test_app_component_passes_inline_attrs_to_root(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    _write(tmp_path, "app_btn.html", '<button class="x">{{ label }}</button>')

    class AppBtn(BaseComponent):
        label: str = ""

    renderer = Renderer.get_default_renderer()
    rendered = renderer.render('<AppBtn label="Hi" hx-post="/foo" hx-target="#bar"/>')

    assert 'hx-post="/foo"' in rendered
    assert 'hx-target="#bar"' in rendered


def test_app_component_inline_class_overrides_template_class(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    _write(tmp_path, "app_box.html", '<div class="base">{{ body }}</div>')

    class AppBox(BaseComponent):
        body: str = ""

    renderer = Renderer.get_default_renderer()
    rendered = renderer.render('<AppBox body="x" class="mt-4"/>')

    assert 'class="mt-4"' in rendered
    assert 'class="base"' not in rendered


def test_multi_root_template_raises(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    _write(tmp_path, "two_roots.html", "<div>a</div><div>b</div>")

    class TwoRoots(BaseComponent):
        pass

    renderer = Renderer.get_default_renderer()
    with pytest.raises(ValueError, match="exactly one root"):
        renderer.render("<TwoRoots/>")
```

(`AppBtn`/`AppBox`/`TwoRoots` resolve to `app_btn.html`/`app_box.html`/`two_roots.html` via the existing PascalCase → snake-case template lookup. If the lookup needs a different filename, adjust the `_write` name to match the renderer's convention — confirm against `tests/unit/test_basecomponent_fallback_no_register.py`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_root_attr_injection.py -v`
Expected: the three new tests FAIL — inline attrs are dropped (parity/override) and the multi-root render does not yet raise.

- [ ] **Step 3: Inject in the renderer**

In `pyjinhx/renderer.py`, replace lines 300-303:

```python
        rendered_markup = stamp_reactive_markup(rendered_markup, component)

        if not emit_assets:
            return Markup(Markup(rendered_markup).unescape())
```

with:

```python
        rendered_markup = stamp_reactive_markup(rendered_markup, component)

        from .base import collect_extra_attrs
        from .root_attrs import apply_root_attrs

        rendered_markup = Markup(
            apply_root_attrs(
                str(rendered_markup),
                component_name=type(component).__name__,
                attrs=collect_extra_attrs(component),
            )
        )

        if not emit_assets:
            return Markup(Markup(rendered_markup).unescape())
```

(The `from .base import ...` is a local import to avoid the `base` ↔ `renderer` cycle. `apply_root_attrs` runs before the `emit_assets` branch so both code paths validate + inject.)

- [ ] **Step 4: Remove the builtin gate + context var in `base.py`**

Delete these two lines in `pyjinhx/base.py` (currently 366-367):

```python
            if type(self).__module__.startswith("pyjinhx.builtins"):
                context["extra_attrs_html"] = render_extra_attrs(self)
```

- [ ] **Step 5: Run the new tests + the existing extra-attrs tests**

Run: `uv run pytest tests/unit/test_root_attr_injection.py tests/unit/test_builtin_extra_attrs.py -v`
Expected: all PASS. `test_builtin_extra_attrs.py` still passes because the same attrs now arrive via injection. (`test_builtin_extra_attrs.py` will be confirmed again after Task 4 removes the template tokens.)

- [ ] **Step 6: Commit**

```bash
git add pyjinhx/renderer.py pyjinhx/base.py tests/unit/test_root_attr_injection.py
git commit -m "feat: inject inline attrs onto every component root; enforce single root"
```

---

### Task 4: Remove `{{ extra_attrs_html }}` from builtin templates; audit single-root

**Files:**
- Modify: every `pyjinhx/builtins/ui/**/*.html` containing `{{ extra_attrs_html }}` (33 templates per `grep -rl`)
- Test: `tests/unit/test_builtin_single_root.py` (new)

**Interfaces:**
- Consumes: injection from Task 3 (so the removed token is replaced by automatic injection).
- Produces: builtins that render exactly one root and receive inline attrs via injection.

- [ ] **Step 1: Write the failing audit test**

```python
# tests/unit/test_builtin_single_root.py
"""Every builtin renders exactly one root element and passes inline attrs."""

import pytest

import pyjinhx.builtins as builtins_pkg
from pyjinhx import Renderer
from pyjinhx.base import BaseComponent


def _builtin_classes():
    seen = []
    for name in dir(builtins_pkg):
        obj = getattr(builtins_pkg, name)
        if isinstance(obj, type) and issubclass(obj, BaseComponent) and obj is not BaseComponent:
            seen.append(obj)
    return seen


@pytest.mark.parametrize("cls", _builtin_classes(), ids=lambda c: c.__name__)
def test_builtin_renders_single_root(cls, tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    # Construct with only id; required fields use defaults. Skip any builtin
    # that cannot be built id-only (its own dedicated test covers it).
    try:
        component = cls(id="x")
    except Exception:
        pytest.skip(f"{cls.__name__} needs required fields; covered elsewhere")
    # render() raises ValueError if the template is not exactly one root.
    str(component.render())
```

- [ ] **Step 2: Run the audit test to find violators**

Run: `uv run pytest tests/unit/test_builtin_single_root.py -v`
Expected: most PASS; any builtin whose template has 2+ top-level elements FAILS with "exactly one root". Note the failing component names — these need a single wrapping root element (or a conditional that still yields one root). From inspection the builtin templates each already have one wrapper root, so expect 0 failures; if any fail, wrap the body in the appropriate single root element and re-run until green.

- [ ] **Step 3: Remove the `{{ extra_attrs_html }}` token from every builtin template**

Run:

```bash
grep -rl "extra_attrs_html" pyjinhx/builtins | while read -r f; do
  python - "$f" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
open(p, "w").write(s.replace("{{ extra_attrs_html }}", ""))
PY
done
grep -rn "extra_attrs_html" pyjinhx/builtins || echo "all tokens removed"
```

Expected: final line prints `all tokens removed`.

- [ ] **Step 4: Run builtin + golden tests**

Run: `uv run pytest tests/unit/test_builtin_single_root.py tests/unit/test_builtin_extra_attrs.py tests/unit/test_golden_builtins.py -v`
Expected: all PASS. If golden snapshots changed only by removal of an empty string (no visible diff), they should be byte-identical; if a golden file legitimately changed because the token previously emitted nothing, no update is needed. If a snapshot diff appears, inspect it — it must be limited to attribute presence/ordering, then regenerate goldens per the repo's snapshot-update convention (check `tests/unit/test_golden_builtins.py` for the update flag).

- [ ] **Step 5: Commit**

```bash
git add pyjinhx/builtins tests/unit/test_builtin_single_root.py
git commit -m "refactor: drop extra_attrs_html token from builtins; audit single root"
```

---

### Task 5: Full suite + docs

**Files:**
- Modify: relevant docs describing `extra_attrs` / attribute pass-through (search first)
- Test: whole suite

- [ ] **Step 1: Confirm `render_extra_attrs` is fully gone**

Run: `grep -rn "render_extra_attrs\|extra_attrs_html" pyjinhx`
Expected: no hits. If any remain (e.g. a builtin `@property` not caught in Task 1), update it to use `collect_extra_attrs` + `serialize_attr`, or delete it if now unused, then re-run.

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest`
Expected: all PASS. Investigate and fix any failure before continuing (a failure here is most likely an existing template/test that assumed multi-root output or the old context var).

- [ ] **Step 3: Update docs**

Run: `grep -rln "extra_attrs_html\|extra_attrs\|pass.through\|builtin" docs README.md 2>/dev/null`
For each doc that documents attribute pass-through as a builtin-only feature or references `{{ extra_attrs_html }}`: rewrite it to state that (a) inline tag attributes pass through to the root element of **any** component automatically, with override semantics, and (b) every component template must have exactly one root element. Remove instructions to place `{{ extra_attrs_html }}` in templates.

- [ ] **Step 4: Commit**

```bash
git add docs README.md
git commit -m "docs: document universal attr pass-through + single-root rule"
```

- [ ] **Step 5: Open the PR**

Push the branch and open a PR summarizing: universal inline attribute pass-through (issue #88), the new single-root invariant, the new `pyjinhx/root_attrs.py` module, and removal of the `extra_attrs_html` mechanism. Reference issue #88.

---

## Notes / known limitations

- Override matching is by exact attribute name and is value-based (`name="..."`). A template that hardcodes a **boolean** attribute with no value (e.g. bare `hidden`) will not be detected as a collision by an inline `hidden="..."`; the inline one is appended. None of the current builtins rely on overriding a bare boolean attr inline, so this is acceptable; revisit only if a real case appears.
- Injection operates on the post-render markup string before the final `Markup(...).unescape()`, mirroring the old context-var path, so quote/escaping behavior for tested values (e.g. `hx-headers` with `"`) is preserved.
