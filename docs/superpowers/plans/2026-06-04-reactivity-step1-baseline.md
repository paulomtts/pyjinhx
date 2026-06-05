# Dependency-Aware Reactivity — Step 1 (Always-Swap Baseline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give pyjinhx components a declarative state→view dependency graph so a mutation route can re-emit exactly the mounted regions that depend on what changed, as HTMX out-of-band (OOB) swaps — without per-session server state.

**Architecture:** Components declare `depends_on` (state keys) and a classmethod `load()` (rebuild from the world). Reactive components are auto-detected (they define `load()`) and stamped with `data-pjx-id/type/hash` on their root element at render time. A shipped client runtime reports a manifest of mounted regions via the `X-PJX-Mounted` header. A new top-level `oob_swaps(dirtied, mounted)` walks that manifest, reloads + renders every region whose `depends_on` intersects `dirtied`, dedups nested regions, and returns concatenated OOB fragments. This is the **always-swap baseline**: everything that matches is swapped. Hash-gating, `render()` parameterization/auto-`load()`, and the `load()` cache are explicitly deferred to later steps.

**Tech Stack:** Python 3.13, Pydantic v2, Jinja2, MarkupSafe, pytest. Plain JS (no build step) for the client runtime.

---

## Scope

This plan implements **only** Implementation Order step 1 from issue #12:

> `load()`, `depends_on`, default `state_hash()`, `data-pjx-*` stamping (type from class `__name__`), the shipped manifest JS + `PJX_MOUNTED_HEADER` constant, and the server walk (dependency filtering + nesting dedup) — no hash gating yet.

**Deferred (named, not built here):**
- **Step 2** — hash-gating (skip regions whose `state_hash()` matches the client-reported hash). `data-pjx-hash` is stamped and reported now, but `oob_swaps` does not yet compare it.
- **Step 3** — folding the walk into `render(*, dirtied=, mounted=)` + the no-import request duck-typing + auto-`load()` for dependents. This baseline ships the walk as a standalone `oob_swaps()` function and leaves `render()` untouched.
- **Step 4** — process-global `load()` cache + reverse index + `threading.Lock`.
- **Instance-keyed deps** (`"user:42"`) — the v1 registry is type-keyed (type-singleton).

Two decisions carried from brainstorming that differ from a naive reading of the issue:
1. **`data-pjx-hash` is stamped & reported from step 1** (server ignores it until step 2), so the wire format does not change between steps.
2. **The walk ships as `oob_swaps(dirtied, mounted)`**, a standalone function, not as `render()` params. `mounted` accepts `str | list | None` only; request duck-typing arrives in step 3.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `pyjinhx/utils.py` *(modify)* | Add `stamp_root_attributes()` (quote-aware root-tag attribute splicer, pure) + `read_client_runtime()` (read bundled JS). Leaf module, no pyjinhx imports — safe to import from both `renderer.py` and `reactive.py`. |
| `pyjinhx/base.py` *(modify)* | Add the public reactive surface to `BaseComponent`: `depends_on` ClassVar, default `state_hash()`, and reactivity auto-detection + warnings wired into `__init_subclass__`. `load()` is **not** defined here — subclasses provide it. |
| `pyjinhx/renderer.py` *(modify)* | Stamp `data-pjx-*` onto reactive components' root tags inside `render_component_with_context`; inject the client runtime once when a `Layout` root renders. Add `runtime_injected` flag to `RenderSession`. |
| `pyjinhx/runtime/pjx.js` *(create)* | Shipped client runtime: on `htmx:configRequest`, collect `[data-pjx-id]` into the `X-PJX-Mounted` header. |
| `pyjinhx/reactive.py` *(create)* | New leaf API module: `PJX_MOUNTED_HEADER`, `client_script()`, `Layout`, and `oob_swaps()` (the server walk). |
| `pyjinhx/__init__.py` *(modify)* | Export `oob_swaps`, `Layout`, `client_script`, `PJX_MOUNTED_HEADER`. |
| `docs/reactivity.md` *(create)* + `mkdocs.yml`, `README.md` *(modify)* | User-facing documentation of the baseline. |
| `tests/3X_*.py`, `tests/ui/reactive/*` | Tests + fixture components/templates. |

**Import-cycle note:** `base.py` imports `renderer.py`; `renderer.py` and `reactive.py` both import only `utils.py` (+ registry) for the new helpers, and `reactive.py` imports `base.py`/`renderer.py`. `__init__.py` imports `base` before `reactive`. No new cycles. The renderer detects `Layout` via a duck-typed `getattr(type(component), "_pjx_layout", False)` marker rather than importing `Layout`, to keep `renderer.py` free of a `reactive.py` import.

**Test conventions (match existing repo):** test files live in `tests/` with a numeric prefix and `_test.py` suffix (next free prefix is `30`). Run with `uv run pytest`. There is no `conftest.py`; tests import fixtures directly (e.g. `from tests.ui.unified_component import UnifiedComponent`). The default Jinja environment auto-detects the project root, so template files placed anywhere under the repo are discoverable by their path relative to the root.

---

## Task 1: Quote-aware root-attribute stamper (`utils.py`)

A pure helper that splices attributes into the first start tag of an HTML fragment without a parse/re-serialize round trip. Used by both the renderer (to stamp `data-pjx-*`) and `oob_swaps` (to add `hx-swap-oob`).

**Files:**
- Modify: `pyjinhx/utils.py`
- Test: `tests/30_stamp_root_attributes_test.py`

- [ ] **Step 1: Write the failing test**

Create `tests/30_stamp_root_attributes_test.py`:

```python
import pytest

from pyjinhx.utils import stamp_root_attributes


def test_stamps_into_first_start_tag():
    result = stamp_root_attributes('<div class="x">hi</div>', {"data-pjx-id": "a"})
    assert result == '<div class="x" data-pjx-id="a">hi</div>'


def test_stamps_multiple_attributes_in_order():
    result = stamp_root_attributes("<span>1</span>", {"data-a": "1", "data-b": "2"})
    assert result == '<span data-a="1" data-b="2">1</span>'


def test_stamps_self_closing_tag_before_slash():
    result = stamp_root_attributes('<img src="a.png"/>', {"data-pjx-id": "a"})
    assert result == '<img src="a.png" data-pjx-id="a"/>'


def test_skips_leading_whitespace_and_comments():
    result = stamp_root_attributes(
        "\n  <!-- note --><section>x</section>", {"data-pjx-id": "a"}
    )
    assert result == '\n  <!-- note --><section data-pjx-id="a">x</section>'


def test_is_quote_aware_for_gt_inside_attribute_value():
    result = stamp_root_attributes('<div data-q="a>b">y</div>', {"data-pjx-id": "a"})
    assert result == '<div data-q="a>b" data-pjx-id="a">y</div>'


def test_escapes_double_quotes_in_values():
    result = stamp_root_attributes("<div>x</div>", {"data-pjx-id": 'a"b'})
    assert result == '<div data-pjx-id="a&quot;b">x</div>'


def test_empty_attributes_returns_input_unchanged():
    assert stamp_root_attributes("<div>x</div>", {}) == "<div>x</div>"


def test_raises_when_no_root_element():
    with pytest.raises(ValueError, match="no root HTML element"):
        stamp_root_attributes("just text, no tags", {"data-pjx-id": "a"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/30_stamp_root_attributes_test.py -v`
Expected: FAIL with `ImportError: cannot import name 'stamp_root_attributes'`.

- [ ] **Step 3: Implement the helper**

Append to `pyjinhx/utils.py`:

```python
def _find_first_start_tag(html: str) -> int:
    """
    Return the index of the '<' that opens the first element start tag, skipping
    leading whitespace, HTML comments, doctype, and processing instructions.
    Returns -1 if no start tag is found.
    """
    cursor = 0
    while True:
        cursor = html.find("<", cursor)
        if cursor == -1:
            return -1
        following = html[cursor + 1 : cursor + 2]
        if following in ("!", "?"):
            end = html.find(">", cursor)
            if end == -1:
                return -1
            cursor = end + 1
            continue
        if following.isalpha():
            return cursor
        cursor += 1


def stamp_root_attributes(html: str, attributes: dict[str, str]) -> str:
    """
    Splice attributes into the first start tag of an HTML fragment.

    Performs a minimal, quote-aware scan to find the end of the first element's
    start tag and inserts the given attributes just before the closing '>' (or
    before the '/' of a '/>' self-closing tag). The rest of the markup is left
    byte-for-byte untouched — no parse/re-serialize round trip.

    Args:
        html: The rendered HTML fragment. Must contain at least one start tag.
        attributes: Attribute name -> value pairs to insert. Values are
            HTML-attribute escaped (double quotes become &quot;).

    Returns:
        The HTML with the attributes spliced into the root element's start tag.

    Raises:
        ValueError: If no start tag is found. Reactive components must render a
            single root element.
    """
    if not attributes:
        return html

    tag_open = _find_first_start_tag(html)
    if tag_open == -1:
        raise ValueError(
            "Cannot stamp reactive attributes: no root HTML element found. "
            "Reactive components must render a single root element."
        )

    cursor = tag_open + 1
    length = len(html)
    quote: str | None = None
    while cursor < length:
        char = html[cursor]
        if quote is not None:
            if char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char == ">":
            break
        cursor += 1
    else:
        raise ValueError(
            "Cannot stamp reactive attributes: unterminated start tag."
        )

    insert_at = cursor - 1 if html[cursor - 1] == "/" else cursor
    rendered_attrs = "".join(
        f' {name}="{str(value).replace(chr(34), "&quot;")}"'
        for name, value in attributes.items()
    )
    return html[:insert_at] + rendered_attrs + html[insert_at:]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/30_stamp_root_attributes_test.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add pyjinhx/utils.py tests/30_stamp_root_attributes_test.py
git commit -m "feat(reactive): add quote-aware root-attribute stamper"
```

---

## Task 2: Reactive surface on `BaseComponent` (`base.py`)

Add `depends_on`, default `state_hash()`, and auto-detection of reactivity (a component is reactive iff it defines `load()`), with developer-friendly warnings.

**Files:**
- Modify: `pyjinhx/base.py:1-11` (imports), `pyjinhx/base.py:43-64` (class body + `__init_subclass__`)
- Test: `tests/31_reactive_surface_test.py`

- [ ] **Step 1: Write the failing test**

Create `tests/31_reactive_surface_test.py`:

```python
import logging
from typing import ClassVar

from pyjinhx import BaseComponent


def test_state_hash_is_stable_and_value_sensitive():
    a = BaseComponent(id="x")
    b = BaseComponent(id="x")
    assert a.state_hash() == b.state_hash()
    assert isinstance(a.state_hash(), str) and len(a.state_hash()) == 16
    assert BaseComponent(id="x", extra="v1").state_hash() != a.state_hash()


def test_reactive_component_is_detected():
    class Counter(BaseComponent):
        remaining: int = 0
        depends_on: ClassVar[set[str]] = {"todos"}

        @classmethod
        def load(cls):
            return cls(id="counter", remaining=0)

    assert Counter._pjx_reactive is True
    assert Counter._pjx_depends_on == frozenset({"todos"})


def test_depends_on_is_not_a_model_field():
    class Widget(BaseComponent):
        depends_on: ClassVar[set[str]] = {"todos"}

        @classmethod
        def load(cls):
            return cls(id="w")

    assert "depends_on" not in Widget.model_fields
    assert Widget(id="w").id == "w"


def test_unannotated_depends_on_assignment_works():
    # Matches the exact syntax shown in issue #12.
    class Plain(BaseComponent):
        depends_on = {"todos"}

        @classmethod
        def load(cls):
            return cls(id="p")

    assert "depends_on" not in Plain.model_fields
    assert Plain._pjx_depends_on == frozenset({"todos"})


def test_plain_component_is_not_reactive():
    class Static(BaseComponent):
        pass

    assert Static._pjx_reactive is False
    assert Static._pjx_depends_on == frozenset()


def test_warns_when_load_without_depends_on(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):

        class Inert(BaseComponent):
            @classmethod
            def load(cls):
                return cls(id="i")

    assert any("Inert" in r.message and "depends_on" in r.message for r in caplog.records)


def test_warns_when_depends_on_without_load(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):

        class NoLoad(BaseComponent):
            depends_on: ClassVar[set[str]] = {"todos"}

    assert any("NoLoad" in r.message and "load()" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/31_reactive_surface_test.py -v`
Expected: FAIL with `AttributeError: type object 'BaseComponent' has no attribute 'state_hash'` (and `_pjx_reactive` missing).

- [ ] **Step 3: Implement the reactive surface**

In `pyjinhx/base.py`, update the imports at the top of the file:

```python
import hashlib
import logging
from typing import Any, ClassVar, Optional
```

(Keep the existing `from markupsafe import Markup`, `from pydantic import ...`, `from .registry import Registry`, `from .renderer import Renderer, RenderSession`, and the `logger = logging.getLogger("pyjinhx")` lines.)

Add the `depends_on` ClassVar inside `BaseComponent`, immediately after the `css` field (around `pyjinhx/base.py:53`):

```python
    depends_on: ClassVar[set[str]] = set()
    """State keys this component derives from. Declaring this plus a load()
    classmethod makes the component reactive (eligible for dependency-aware OOB
    swaps via oob_swaps())."""
```

Replace the existing `__init_subclass__` (`pyjinhx/base.py:61-64`) with:

```python
    def __init_subclass__(cls, **kwargs):
        """Register the component class and configure its reactivity at definition time."""
        super().__init_subclass__(**kwargs)
        Registry.register_class(cls)
        cls._configure_reactivity()

    @classmethod
    def _configure_reactivity(cls) -> None:
        """
        Detect whether this subclass is reactive and normalize its dependencies.

        A component is reactive iff it defines a ``load()`` classmethod. The
        derived flags are stored as plain class attributes (not Pydantic fields)
        so they are inherited by further subclasses and never validated.
        """
        has_load = callable(getattr(cls, "load", None))
        declared = set(getattr(cls, "depends_on", None) or ())
        cls._pjx_reactive = has_load
        cls._pjx_depends_on = frozenset(declared)

        if has_load and not declared:
            logger.warning(
                "%s defines load() but no depends_on; it will never match a "
                "dirtied key and is effectively inert.",
                cls.__name__,
            )
        if declared and not has_load:
            logger.warning(
                "%s declares depends_on=%s but no load(); it cannot be reloaded "
                "for reactive OOB swaps.",
                cls.__name__,
                declared,
            )

    def state_hash(self) -> str:
        """
        Return a stable content hash of this component's state.

        Used to gate reactive OOB swaps so a region whose value did not change is
        not re-sent. The default hashes ``model_dump_json()``; override for custom
        hashing. In the always-swap baseline (step 1) this value is stamped onto
        the root element and reported by the client, but not yet used for gating.
        """
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()[:16]
```

Note: `_pjx_reactive` / `_pjx_depends_on` are intentionally **not** declared in the class body (no annotation) — they are set imperatively in `_configure_reactivity`. Callers must read them with a default, e.g. `getattr(type(component), "_pjx_reactive", False)`, because `BaseComponent` itself never runs `__init_subclass__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/31_reactive_surface_test.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `uv run pytest tests/ -q`
Expected: PASS (all existing tests still green — the new ClassVar and methods are additive).

- [ ] **Step 6: Commit**

```bash
git add pyjinhx/base.py tests/31_reactive_surface_test.py
git commit -m "feat(reactive): add depends_on, state_hash, and reactivity auto-detection"
```

---

## Task 3: Stamp reactive components in the renderer (`renderer.py`)

When a reactive component renders (root or nested), splice `data-pjx-id/type/hash` onto its root element so the client can report it and so nesting-dedup containment checks work.

**Files:**
- Modify: `pyjinhx/renderer.py:19-24` (utils import), `pyjinhx/renderer.py:601-605` (after custom-tag expansion)
- Test: `tests/32_reactive_stamping_test.py`

- [ ] **Step 1: Write the failing test**

Create `tests/32_reactive_stamping_test.py`:

```python
from typing import ClassVar

from pyjinhx import BaseComponent
from tests.ui.unified_component import UnifiedComponent


class StampCounter(BaseComponent):
    remaining: int = 0
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls):
        return cls(id="stamp-counter", remaining=0)


def test_reactive_root_is_stamped():
    counter = StampCounter(id="c1", remaining=3)
    html = str(counter._render(source="<span class='c'>{{ remaining }} left</span>"))
    assert html.startswith('<span class=\'c\' data-pjx-id="c1"')
    assert 'data-pjx-type="StampCounter"' in html
    assert f'data-pjx-hash="{counter.state_hash()}"' in html
    assert ">3 left</span>" in html


def test_non_reactive_component_is_not_stamped():
    html = str(UnifiedComponent(id="u1", text="hi")._render())
    assert "data-pjx-id" not in html
    assert "data-pjx-type" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/32_reactive_stamping_test.py -v`
Expected: FAIL — `test_reactive_root_is_stamped` fails because no `data-pjx-*` attributes are present.

- [ ] **Step 3: Wire stamping into the renderer**

In `pyjinhx/renderer.py`, add `stamp_root_attributes` to the existing `from .utils import (...)` block (`pyjinhx/renderer.py:19-24`):

```python
from .utils import (
    detect_root_directory,
    pascal_case_to_kebab_case,
    pascal_case_to_snake_case,
    stamp_root_attributes,
    tag_name_to_template_filenames,
)
```

In `render_component_with_context`, immediately after the custom-tag expansion line (`pyjinhx/renderer.py:602-604`):

```python
        rendered_markup = self._expand_custom_tags(
            rendered_markup, base_context=render_context, session=session
        )

        if getattr(type(component), "_pjx_reactive", False):
            rendered_markup = stamp_root_attributes(
                rendered_markup,
                {
                    "data-pjx-id": component.id,
                    "data-pjx-type": type(component).__name__,
                    "data-pjx-hash": component.state_hash(),
                },
            )
```

This runs for every reactive component whether it is the root render or a nested child (each component renders its own markup through this method), and **before** the `is_root` style/script injection, so the attributes land on the component's own root element rather than on an injected `<style>`/`<script>`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/32_reactive_stamping_test.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS (non-reactive components are untouched, so existing snapshot tests still match).

- [ ] **Step 6: Commit**

```bash
git add pyjinhx/renderer.py tests/32_reactive_stamping_test.py
git commit -m "feat(reactive): stamp data-pjx-* onto reactive component roots"
```

---

## Task 4: Client runtime, `PJX_MOUNTED_HEADER`, and `client_script()` (`runtime/pjx.js`, `utils.py`, `reactive.py`)

Ship the JS that reports the manifest header, plus the constant and the `client_script()` helper for raw-Jinja shells.

**Files:**
- Create: `pyjinhx/runtime/pjx.js`
- Modify: `pyjinhx/utils.py` (add `read_client_runtime`)
- Create: `pyjinhx/reactive.py` (constant + `client_script`)
- Test: `tests/33_client_runtime_test.py`

- [ ] **Step 1: Write the failing test**

Create `tests/33_client_runtime_test.py`:

```python
from markupsafe import Markup

from pyjinhx.reactive import PJX_MOUNTED_HEADER, client_script
from pyjinhx.utils import read_client_runtime


def test_header_constant():
    assert PJX_MOUNTED_HEADER == "X-PJX-Mounted"


def test_runtime_source_reports_manifest_header():
    source = read_client_runtime()
    assert "htmx:configRequest" in source
    assert "X-PJX-Mounted" in source
    assert "data-pjx-id" in source


def test_client_script_wraps_runtime_in_script_tag():
    script = client_script()
    assert isinstance(script, Markup)
    assert script.startswith("<script>")
    assert script.endswith("</script>")
    assert "htmx:configRequest" in script
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/33_client_runtime_test.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pyjinhx.reactive'`.

- [ ] **Step 3a: Create the client runtime JS**

Create `pyjinhx/runtime/pjx.js`:

```javascript
(function () {
  function pjxManifest() {
    return Array.prototype.map.call(
      document.querySelectorAll("[data-pjx-id]"),
      function (el) {
        return {
          id: el.dataset.pjxId,
          type: el.dataset.pjxType,
          hash: el.dataset.pjxHash,
        };
      }
    );
  }

  document.body.addEventListener("htmx:configRequest", function (evt) {
    evt.detail.headers["X-PJX-Mounted"] = JSON.stringify(pjxManifest());
  });
})();
```

- [ ] **Step 3b: Add `read_client_runtime` to utils**

Append to `pyjinhx/utils.py`:

```python
def read_client_runtime() -> str:
    """Return the bundled pyjinhx client runtime JavaScript source."""
    runtime_path = os.path.join(os.path.dirname(__file__), "runtime", "pjx.js")
    with open(runtime_path, encoding="utf-8") as runtime_file:
        return runtime_file.read()
```

- [ ] **Step 3c: Create `reactive.py` with the constant and `client_script`**

Create `pyjinhx/reactive.py`:

```python
from __future__ import annotations

import logging

from markupsafe import Markup

from .utils import read_client_runtime

logger = logging.getLogger("pyjinhx")

PJX_MOUNTED_HEADER = "X-PJX-Mounted"
"""Name of the HTTP header carrying the client's mounted-region manifest."""


def client_script() -> Markup:
    """
    Return the pyjinhx client runtime wrapped in a ``<script>`` tag.

    Drop this into a page shell (e.g. a raw Jinja layout) to emit the
    ``X-PJX-Mounted`` manifest header on every htmx request. When the page shell
    subclasses ``Layout`` the runtime is injected automatically and you do not
    need to call this.
    """
    return Markup(f"<script>{read_client_runtime()}</script>")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/33_client_runtime_test.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pyjinhx/runtime/pjx.js pyjinhx/utils.py pyjinhx/reactive.py tests/33_client_runtime_test.py
git commit -m "feat(reactive): ship client manifest runtime and client_script helper"
```

---

## Task 5: `Layout` base class + auto-injected runtime (`reactive.py`, `renderer.py`)

Page shells subclass `Layout`; rendering a `Layout` root injects the runtime once.

**Files:**
- Modify: `pyjinhx/renderer.py:93-96` (`RenderSession` fields), `pyjinhx/renderer.py:626-633` (root injection), `pyjinhx/renderer.py:19-24` (utils import)
- Modify: `pyjinhx/reactive.py` (add `Layout`)
- Test: `tests/34_layout_runtime_test.py`

- [ ] **Step 1: Write the failing test**

Create `tests/34_layout_runtime_test.py`:

```python
from pyjinhx import BaseComponent
from pyjinhx.reactive import Layout


class Page(Layout):
    pass


class PlainShell(BaseComponent):
    pass


def test_layout_root_injects_runtime_once():
    html = str(Page(id="page")._render(source="<html><body>hi</body></html>"))
    assert "htmx:configRequest" in html
    assert "X-PJX-Mounted" in html
    assert html.count("htmx:configRequest") == 1


def test_non_layout_root_does_not_inject_runtime():
    html = str(PlainShell(id="shell")._render(source="<html><body>hi</body></html>"))
    assert "htmx:configRequest" not in html


def test_layout_marker_is_inherited():
    assert getattr(Page, "_pjx_layout", False) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/34_layout_runtime_test.py -v`
Expected: FAIL with `ImportError: cannot import name 'Layout'`.

- [ ] **Step 3a: Add `Layout` to `reactive.py`**

Append to `pyjinhx/reactive.py`:

```python
from .base import BaseComponent


class Layout(BaseComponent):
    """
    Base class for full-page shells.

    Rendering a ``Layout`` subclass as the page root injects the pyjinhx client
    runtime once, so mounted reactive regions report their manifest via the
    ``X-PJX-Mounted`` header. Subclass it for your page shell and provide a
    template as usual; fragment endpoints render ordinary components, so the
    runtime is never injected into partial responses.
    """


Layout._pjx_layout = True
```

The marker is set as a plain class attribute (no annotation) so Pydantic never treats it as a field, and so the renderer can detect it via `getattr(...)` without importing `Layout`.

- [ ] **Step 3b: Add the `runtime_injected` flag to `RenderSession`**

In `pyjinhx/renderer.py`, add a field to the `RenderSession` dataclass (after `collected_css_files`, `pyjinhx/renderer.py:96`):

```python
    runtime_injected: bool = False
```

- [ ] **Step 3c: Inject the runtime for `Layout` roots**

Add `read_client_runtime` to the `from .utils import (...)` block in `pyjinhx/renderer.py`:

```python
from .utils import (
    detect_root_directory,
    pascal_case_to_kebab_case,
    pascal_case_to_snake_case,
    read_client_runtime,
    stamp_root_attributes,
    tag_name_to_template_filenames,
)
```

In `render_component_with_context`, inside the `if is_root:` block, add the runtime injection just before the `if self._inline_js:` branch (`pyjinhx/renderer.py:627-633`):

```python
        if is_root:
            if self._inline_css:
                self._collect_extra_css(component, session)
                rendered_markup = self._inject_styles(rendered_markup, session)
            if (
                self._inline_js
                and getattr(type(component), "_pjx_layout", False)
                and not session.runtime_injected
            ):
                session.scripts.insert(0, read_client_runtime())
                session.runtime_injected = True
            if self._inline_js:
                self._collect_extra_javascript(component, session)
                rendered_markup = self._inject_scripts(rendered_markup, session)
```

The runtime is inserted at the front of `session.scripts` so it loads before component scripts, and `_inject_scripts` wraps it in a `<script>` tag like any other collected script.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/34_layout_runtime_test.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyjinhx/renderer.py pyjinhx/reactive.py tests/34_layout_runtime_test.py
git commit -m "feat(reactive): add Layout base class with auto-injected client runtime"
```

---

## Task 6: The server walk — `oob_swaps()` (`reactive.py`)

Parse the manifest, filter by dependency, reload + render each affected reactive region, drop nested children, and emit concatenated OOB fragments.

**Files:**
- Modify: `pyjinhx/reactive.py` (add `oob_swaps` + helpers)
- Create fixtures: `tests/ui/reactive/__init__.py`, `tests/ui/reactive/store.py`, `tests/ui/reactive/counter.py`, `tests/ui/reactive/counter.html`, `tests/ui/reactive/clear_button.py`, `tests/ui/reactive/clear-button.html`, `tests/ui/reactive/panel.py`, `tests/ui/reactive/panel.html`
- Test: `tests/35_oob_swaps_test.py`

- [ ] **Step 1: Create the fixture components and templates**

Create `tests/ui/reactive/__init__.py` (empty file):

```python
```

Create `tests/ui/reactive/store.py`:

```python
"""Mutable in-memory state for reactive fixture components."""

state = {"remaining": 0, "completed": 0}
```

Create `tests/ui/reactive/counter.py`:

```python
from typing import ClassVar

from pyjinhx import BaseComponent

from .store import state


class Counter(BaseComponent):
    remaining: int = 0
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "Counter":
        return cls(id="counter", remaining=state["remaining"])
```

Create `tests/ui/reactive/counter.html`:

```html
<span class="counter">{{ remaining }} left</span>
```

Create `tests/ui/reactive/clear_button.py`:

```python
from typing import ClassVar

from pyjinhx import BaseComponent

from .store import state


class ClearButton(BaseComponent):
    completed: int = 0
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "ClearButton":
        return cls(id="clear-btn", completed=state["completed"])
```

Create `tests/ui/reactive/clear-button.html`:

```html
<button class="clear">Clear ({{ completed }})</button>
```

Create `tests/ui/reactive/panel.py`:

```python
from typing import ClassVar, Optional

from pyjinhx import BaseComponent

from .counter import Counter


class Panel(BaseComponent):
    child: Optional[Counter] = None
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "Panel":
        return cls(id="panel", child=Counter.load())
```

Create `tests/ui/reactive/panel.html`:

```html
<div class="panel">{{ child }}</div>
```

- [ ] **Step 2: Write the failing test**

Create `tests/35_oob_swaps_test.py`:

```python
from markupsafe import Markup

from pyjinhx import oob_swaps
from tests.ui.reactive import store
from tests.ui.reactive.counter import Counter  # noqa: F401 (registers class)
from tests.ui.reactive.clear_button import ClearButton  # noqa: F401
from tests.ui.reactive.panel import Panel  # noqa: F401
from tests.ui.unified_component import UnifiedComponent  # noqa: F401


def _counter_entry():
    return {"id": "counter", "type": "Counter", "hash": "stale"}


def _clear_entry():
    return {"id": "clear-btn", "type": "ClearButton", "hash": "stale"}


def test_swaps_all_dependents_of_dirtied_key():
    store.state["remaining"] = 2
    store.state["completed"] = 1
    out = str(oob_swaps({"todos"}, [_counter_entry(), _clear_entry()]))
    assert "outerHTML:[data-pjx-id='counter']" in out
    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    assert "2 left" in out
    assert "Clear (1)" in out


def test_returns_empty_markup_when_no_dependency_matches():
    out = oob_swaps({"users"}, [_counter_entry()])
    assert isinstance(out, Markup)
    assert str(out) == ""


def test_empty_or_none_manifest_returns_empty():
    assert str(oob_swaps({"todos"}, None)) == ""
    assert str(oob_swaps({"todos"}, "")) == ""
    assert str(oob_swaps({"todos"}, [])) == ""


def test_unknown_type_is_ignored():
    out = oob_swaps({"todos"}, [{"id": "ghost", "type": "DoesNotExist", "hash": "x"}])
    assert str(out) == ""


def test_non_reactive_type_is_ignored():
    out = oob_swaps({"todos"}, [{"id": "u1", "type": "UnifiedComponent", "hash": "x"}])
    assert str(out) == ""


def test_accepts_raw_json_string_manifest():
    store.state["remaining"] = 5
    out = str(oob_swaps({"todos"}, '[{"id":"counter","type":"Counter","hash":"x"}]'))
    assert "5 left" in out
    assert "outerHTML:[data-pjx-id='counter']" in out


def test_invalid_json_string_is_ignored():
    assert str(oob_swaps({"todos"}, "not json")) == ""


def test_nested_child_is_deduplicated():
    store.state["remaining"] = 3
    manifest = [
        {"id": "panel", "type": "Panel", "hash": "x"},
        {"id": "counter", "type": "Counter", "hash": "x"},
    ]
    out = str(oob_swaps({"todos"}, manifest))
    # The panel is swapped (its fresh HTML already contains the counter)...
    assert "outerHTML:[data-pjx-id='panel']" in out
    # ...and the counter is NOT swapped on its own.
    assert "outerHTML:[data-pjx-id='counter']" not in out
    # The counter's content rides inside the panel swap.
    assert "3 left" in out
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/35_oob_swaps_test.py -v`
Expected: FAIL with `ImportError: cannot import name 'oob_swaps' from 'pyjinhx'`.

- [ ] **Step 4: Implement `oob_swaps` and helpers**

Append to `pyjinhx/reactive.py` (add `import json` and `from typing import Any` to the top of the file, and the `Registry`/`Renderer`/`stamp_root_attributes` imports):

```python
import json
from typing import Any

from .registry import Registry
from .renderer import Renderer
from .utils import stamp_root_attributes


def _parse_mounted(mounted: str | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if mounted is None or mounted == "":
        return []
    if isinstance(mounted, list):
        return mounted
    if isinstance(mounted, str):
        try:
            parsed = json.loads(mounted)
        except json.JSONDecodeError:
            logger.warning("Could not parse %s manifest as JSON; ignoring.", PJX_MOUNTED_HEADER)
            return []
        return parsed if isinstance(parsed, list) else []
    raise TypeError(
        "mounted must be the X-PJX-Mounted header string, a parsed list, or None. "
        "Passing a request object is supported once render() parameterization lands (step 3)."
    )


def _drop_nested(rendered: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    Drop any rendered region whose data-pjx-id marker appears inside another
    region's HTML — the parent's fresh HTML already contains the child, so a
    separate swap would be redundant (and would fight the parent's swap).
    """
    surviving: list[tuple[str, str]] = []
    for index, (component_id, html) in enumerate(rendered):
        marker = f'data-pjx-id="{component_id}"'
        nested_in_other = any(
            marker in other_html
            for other_index, (_, other_html) in enumerate(rendered)
            if other_index != index
        )
        if not nested_in_other:
            surviving.append((component_id, html))
    return surviving


def oob_swaps(
    dirtied: set[str],
    mounted: str | list[dict[str, Any]] | None,
) -> Markup:
    """
    Compute out-of-band swap fragments for every mounted reactive region whose
    declared dependencies intersect the dirtied state keys.

    This is the always-swap baseline (issue #12, implementation order step 1):
    every region depending on a dirtied key is reloaded and swapped. Hash-gating
    (skipping regions whose value did not change) is layered on in step 2.

    Args:
        dirtied: The state keys the route mutated (e.g. {"todos"}).
        mounted: The client manifest from the X-PJX-Mounted header — the raw JSON
            string, an already-parsed list of {"id", "type", "hash"} dicts, or
            None/"".

    Returns:
        A single Markup of concatenated OOB swap fragments, each carrying
        hx-swap-oob. Empty Markup if nothing needs swapping.
    """
    manifest = _parse_mounted(mounted)
    if not manifest:
        return Markup("")

    classes = Registry.get_classes()
    renderer = Renderer.get_default_renderer(inline_js=False, inline_css=False)

    rendered: list[tuple[str, str]] = []
    seen_types: set[str] = set()
    for entry in manifest:
        component_type = entry.get("type")
        component_id = entry.get("id")
        if not component_type or not component_id:
            continue

        component_class = classes.get(component_type)
        if component_class is None:
            continue
        if not getattr(component_class, "_pjx_reactive", False):
            continue
        if not (getattr(component_class, "_pjx_depends_on", frozenset()) & dirtied):
            continue

        if component_type in seen_types:
            logger.warning(
                "Multiple mounted instances of reactive type %s; the v1 "
                "type-singleton model reloads it once. Instance-keyed deps are "
                "deferred.",
                component_type,
            )
            continue
        seen_types.add(component_type)

        instance = component_class.load()
        instance.id = component_id
        rendered.append((component_id, str(instance._render(_renderer=renderer))))

    surviving = _drop_nested(rendered)
    if not surviving:
        return Markup("")

    fragments = [
        stamp_root_attributes(
            html, {"hx-swap-oob": f"outerHTML:[data-pjx-id='{component_id}']"}
        )
        for component_id, html in surviving
    ]
    return Markup("\n".join(fragments))
```

Notes:
- Rendering uses a renderer with `inline_js=False, inline_css=False` so OOB fragments contain **only** the stamped element — no stray `<style>`/`<script>` siblings (those are already loaded by the initial page render and, lacking `hx-swap-oob`, would otherwise be swapped into the main target).
- `instance.id = component_id` forces the freshly loaded instance to carry the mounted id, so the stamped `data-pjx-id` (added during `_render`) matches the OOB selector.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/35_oob_swaps_test.py -v`
Expected: PASS (8 passed).

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyjinhx/reactive.py tests/ui/reactive tests/35_oob_swaps_test.py
git commit -m "feat(reactive): add oob_swaps server walk with dependency filtering and nesting dedup"
```

---

## Task 7: Export the public API (`__init__.py`)

**Files:**
- Modify: `pyjinhx/__init__.py`
- Test: `tests/36_public_api_test.py`

- [ ] **Step 1: Write the failing test**

Create `tests/36_public_api_test.py`:

```python
import pyjinhx


def test_reactive_api_is_exported():
    from pyjinhx import (
        Layout,
        PJX_MOUNTED_HEADER,
        client_script,
        oob_swaps,
    )

    assert PJX_MOUNTED_HEADER == "X-PJX-Mounted"
    assert callable(oob_swaps)
    assert callable(client_script)
    assert issubclass(Layout, pyjinhx.BaseComponent)


def test_names_in_all():
    for name in ("oob_swaps", "Layout", "client_script", "PJX_MOUNTED_HEADER"):
        assert name in pyjinhx.__all__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/36_public_api_test.py -v`
Expected: FAIL with `ImportError: cannot import name 'oob_swaps' from 'pyjinhx'`.

- [ ] **Step 3: Update `__init__.py`**

Replace the contents of `pyjinhx/__init__.py` with:

```python
from .base import BaseComponent
from .dataclasses import Tag
from .finder import Finder
from .parser import Parser
from .reactive import PJX_MOUNTED_HEADER, Layout, client_script, oob_swaps
from .registry import Registry
from .renderer import Renderer

__all__ = [
    "BaseComponent",
    "Renderer",
    "Finder",
    "Parser",
    "Registry",
    "Tag",
    "Layout",
    "oob_swaps",
    "client_script",
    "PJX_MOUNTED_HEADER",
]
```

`reactive` is imported after `base` (and `base` pulls in `renderer`), so all of `reactive`'s imports (`base`, `renderer`, `registry`, `utils`) are already resolvable — no import cycle.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/36_public_api_test.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyjinhx/__init__.py tests/36_public_api_test.py
git commit -m "feat(reactive): export oob_swaps, Layout, client_script, PJX_MOUNTED_HEADER"
```

---

## Task 8: Documentation

Document the baseline so users can adopt it; note what is deferred.

**Files:**
- Create: `docs/reactivity.md`
- Modify: `mkdocs.yml:66-73` (add nav entry under Guide)
- Modify: `README.md` (add a short reactivity section near the feature list)

- [ ] **Step 1: Write the docs page**

Create `docs/reactivity.md`:

````markdown
# Reactivity (Dependency-Aware OOB Swaps)

pyjinhx owns **composition**; HTMX owns **transport and swap**. Between them sits
the **state→view dependency graph** — which regions must change when a piece of
state changes. pyjinhx lets you declare that graph once, on the components, so a
mutation route re-emits exactly the mounted regions that depend on what changed.

This is the **always-swap baseline**: every region that depends on a dirtied key
is reloaded and swapped. (Hash-gating to skip unchanged regions, `render()`
integration, and a `load()` cache are planned follow-ups.)

## 1. Make a component reactive

A component is reactive when it declares `depends_on` and a `load()` classmethod:

```python
from typing import ClassVar
from pyjinhx import BaseComponent

class Counter(BaseComponent):
    remaining: int
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "Counter":
        return cls(id="counter", remaining=db.remaining())
```

- `depends_on` — the named state keys this component derives from.
- `load()` — rebuilds the component from the current world, independent of any route.
- `state_hash()` is provided by `BaseComponent` (hash of `model_dump_json()`); override only for custom hashing.

Reactive components are stamped with `data-pjx-id`, `data-pjx-type` (the class
name), and `data-pjx-hash` on their root element automatically.

## 2. Ship the client runtime

Subclass `Layout` for your page shell — the manifest runtime is injected once on
full-page renders:

```python
from pyjinhx import Layout

class AppShell(Layout):
    ...  # app_shell.html is your full page template
```

Or, in a raw Jinja layout, drop in `client_script()`:

```python
from pyjinhx import client_script

# in your template context
{"pjx_runtime": client_script()}
```
```html
<body>
  ...
  {{ pjx_runtime }}
</body>
```

The runtime attaches a manifest of mounted regions to every htmx request via the
`X-PJX-Mounted` header.

## 3. Emit OOB swaps from your route

In a mutation route, render your primary response as usual, then append the OOB
swaps for everything that depends on what you changed:

```python
from pyjinhx import oob_swaps, PJX_MOUNTED_HEADER

@app.post("/todos/{id}/toggle")
def toggle(id, request):
    db.toggle(id)
    primary = TodoItem(id=id, text=..., done=...).render()
    swaps = oob_swaps(
        dirtied={"todos"},
        mounted=request.headers.get(PJX_MOUNTED_HEADER, ""),
    )
    return primary + swaps
```

`oob_swaps`:
- keeps only mounted regions whose `depends_on` intersects `dirtied`,
- calls each region's `load()` and re-renders it,
- drops any region nested inside another swapped region (the parent already contains it),
- returns concatenated `hx-swap-oob` fragments (empty if nothing matched).

The dependency graph lives in exactly one place — the `depends_on` declarations —
not smeared across endpoints. Adding a progress bar that declares
`depends_on = {"todos"}` makes it participate automatically; no endpoint changes.

## Boundaries (current baseline)

- **Always-swap**: hash-gating is not applied yet — a matching region is always re-sent.
- **Type-singleton**: one mounted instance per reactive type is reloaded; instance-keyed deps (`"user:42"`) are deferred.
- **`mounted` accepts** the raw header string, a parsed list, or `None`. Passing a request object directly arrives with `render()` integration.
````

- [ ] **Step 2: Add the nav entry**

In `mkdocs.yml`, add a `Reactivity` entry to the `Guide` section (after `Configuration`, around `mkdocs.yml:73`):

```yaml
      - Configuration: guide/configuration.md
      - Reactivity: reactivity.md
```

- [ ] **Step 3: Add a README section**

In `README.md`, add a short section (placement: after the existing feature/usage overview — search for the features list and insert below it):

```markdown
## Reactivity (dependency-aware OOB swaps)

Declare a component's state dependencies once and let mutation routes re-emit
exactly the mounted regions that depend on what changed:

```python
from typing import ClassVar
from pyjinhx import BaseComponent, oob_swaps, PJX_MOUNTED_HEADER

class Counter(BaseComponent):
    remaining: int
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "Counter":
        return cls(id="counter", remaining=db.remaining())

@app.post("/todos/{id}/toggle")
def toggle(id, request):
    db.toggle(id)
    return TodoItem(id=id, ...).render() + oob_swaps(
        dirtied={"todos"},
        mounted=request.headers.get(PJX_MOUNTED_HEADER, ""),
    )
```

See [the reactivity guide](docs/reactivity.md) for details.
```

- [ ] **Step 4: Verify docs build (if mkdocs available) and tests still pass**

Run: `uv run pytest tests/ -q`
Expected: PASS.
Run (optional, dev group): `uv run mkdocs build --strict`
Expected: build succeeds with the new page in the nav.

- [ ] **Step 5: Commit**

```bash
git add docs/reactivity.md mkdocs.yml README.md
git commit -m "docs(reactive): document the always-swap reactivity baseline"
```

---

## Final: Push the branch

- [ ] **Run the full suite one more time**

Run: `uv run pytest tests/ -q`
Expected: PASS (all tasks green).

- [ ] **Push**

```bash
git push -u origin claude/issue-12-brainstorm-7UK4a
```

(Retry on network errors with exponential backoff: 2s, 4s, 8s, 16s.)

---

## Self-Review

**Spec coverage (issue #12, implementation order step 1):**
- `load()` — convention defined; fixtures + `oob_swaps` invoke it (Tasks 2, 6). ✅
- `depends_on` — ClassVar surface + normalization (Task 2). ✅
- default `state_hash()` — Task 2. ✅
- `data-pjx-*` stamping, type from class `__name__` — Tasks 1, 3. ✅
- shipped manifest JS — Task 4. ✅
- `PJX_MOUNTED_HEADER` constant — Tasks 4, 7. ✅
- server walk: dependency filtering — Task 6 (`depends_on & dirtied`). ✅
- server walk: nesting dedup — Task 6 (`_drop_nested`). ✅
- no hash gating yet — confirmed: `data-pjx-hash` stamped/reported but never compared. ✅
- relevant code touched: `base.py`, `registry.py` (read via `Registry.get_classes`), new `.js` runtime — ✅ (`registry.py` needs no edit; the class registry already maps names→classes, which `oob_swaps` consumes).

**Type/name consistency check:**
- `stamp_root_attributes(html, attributes)` — same signature in Tasks 1, 3, 6. ✅
- `_pjx_reactive` / `_pjx_depends_on` set in Task 2, read via `getattr` in Tasks 3, 6. ✅
- `_pjx_layout` set in Task 5, read in Task 5 renderer. ✅
- `read_client_runtime()` defined in Task 4, used in Tasks 4, 5. ✅
- `PJX_MOUNTED_HEADER = "X-PJX-Mounted"` — consistent across Tasks 4, 6, 7, 8 and matches the JS string in `pjx.js`. ✅
- `oob_swaps(dirtied, mounted)` — consistent across Tasks 6, 7, 8. ✅
- Fixture class names (`Counter`, `ClearButton`, `Panel`) and template filenames (`counter.html`, `clear-button.html`, `panel.html`) follow the kebab/snake auto-discovery rules. ✅

**Placeholder scan:** No TBD/TODO/"add error handling"/"similar to Task N" — every code step contains complete code. ✅

**Note for the implementer:** `_pjx_reactive`/`_pjx_depends_on`/`_pjx_layout` are deliberately set imperatively (not declared as annotated class attributes) to avoid Pydantic treating them as fields or private attributes. If a future change needs them on `BaseComponent` itself, add them via `getattr` defaults rather than annotated class bodies.
````
