# Single-root invariant + universal attribute injection

**Date:** 2026-06-17
**Status:** Approved (design)
**Related:** Issue #88 (inline attribute pass-through gated to builtins)

## Problem

Arbitrary inline tag attributes on a PascalCase tag (`hx-*`, `data-*`, `aria-*`, etc.)
are only rendered onto the root element for **builtin** components. App-defined
components silently drop them.

Today this is wired through two coupled mechanisms in `base.py`:

```python
if type(self).__module__.startswith("pyjinhx.builtins"):
    context["extra_attrs_html"] = render_extra_attrs(self)
```

and a `{{ extra_attrs_html }}` token that each builtin template must place by hand
on its root element. This:

- gates pass-through to builtins only, and
- relies on template-author discipline (the `{{ extra_attrs_html }}` token) even
  for builtins.

The stray attributes already reach `model_extra` for every component (Pydantic
`extra="allow"`); they are simply never rendered for app components.

## Goal

Inline attribute pass-through should **just work** on every component, with no
template-author discipline and no builtin/app distinction. Achieve this by making
single-root a universal invariant (React-style) and injecting attributes onto that
root automatically after render.

Backward compatibility is explicitly **not** a goal — existing multi-root templates
are expected to be fixed.

## Decisions

- **Root rule:** every component's rendered output must contain **exactly one**
  top-level element. 0 (text-only) or 2+ siblings → error.
- **Collisions:** inline attributes **override** any colliding attribute the
  template hardcoded on the root, including `class` and `style` (full replace, not
  merge).
- **Multi/zero root:** raise a clear error naming the component.
- **`render_extra_attrs`:** delete unless an external caller remains (lean delete).

## Design

### 1. Single-root invariant (all components)

Every component's rendered HTML must contain exactly one top-level element.
Validated at render time, so conditional roots resolve naturally:

```jinja
{% if href %}<a ...>{% else %}<button ...>{% endif %}
```

renders to one root and passes. Comments and whitespace surrounding the root are
ignored. Because a parent's template embeds its children as already-rendered HTML
nested inside the parent's root, validating each component as it renders gives
recursive validation of the whole tree for free.

Errors:

- 0 top-level elements (e.g. a text-only template) → error.
- 2+ top-level elements → error.

Error message names the component type and states that exactly one root element is
required.

### 2. `resolve_root(html) -> RootSpan` (one fused pass)

A single `HTMLParser`-based scan that:

- skips leading whitespace, comments, and doctype;
- finds the first start tag (the root) and records its opening-tag span and parsed
  attributes;
- tracks element depth, correctly handling void elements (`input`, `br`, `img`,
  `hr`, `meta`, `link`, etc.) and XML-style self-closing tags, so it knows when the
  root has closed;
- detects any second top-level element (and the zero-element case) and raises.

Returns the root opening tag's character span plus its existing attributes as an
ordered mapping. This runs for **every** component render (validation is always on).

### 3. `collect_extra_attrs(component) -> dict[str, str]`

Refactored out of today's `render_extra_attrs`. Produces an **ordered dict** (not a
pre-joined string) by merging:

- the explicit `extra_attrs` field, then
- stray `model_extra` entries that are strings with valid attribute names.

Reuses the existing name validation (`_ATTR_NAME_RE`) and the "value must not
contain both quote types" rule. Order: `extra_attrs` first, then `model_extra`
additions.

### 4. Injection

After `resolve_root` confirms the single root, if `collect_extra_attrs` is
non-empty:

- start from the root tag's existing attributes (ordered);
- apply inline attributes with **override** semantics — a colliding key (including
  `class`/`style`) takes the inline value; new keys are appended in order;
- re-serialize the full attribute set with the existing quote-safe rules (prefer
  `"`, fall back to `'` when the value contains `"`);
- splice the rebuilt opening tag back into the rendered string at the root span.

If `collect_extra_attrs` is empty, the rendered string is returned unchanged (root
validation still ran).

### 5. Integration point

In `base.py`, immediately after
`renderer.render_component_with_context(self, ...)` returns the HTML string:

1. always call `resolve_root` (validate the single-root invariant);
2. if extras present, inject them into the root span.

No HTML-vs-Python construction distinction: the invariant and injection apply to any
component that renders a template.

### 6. Removals (simplification)

- Drop the `pyjinhx.builtins` module gate and the `extra_attrs_html` context var in
  `base.py`.
- Remove `{{ extra_attrs_html }}` from all builtin templates (it would double-apply
  under automatic injection).
- Delete `render_extra_attrs` unless an external caller remains.
- Audit every builtin template to confirm it has exactly one root.

## Testing

- **Pass-through parity:** an app `BaseComponent` subclass and a generic
  template-only component both emit inline `hx-*`/`data-*`/`aria-*` on the root,
  matching builtin behavior.
- **Override:** template root `class="card"` + inline `class="mt-4"` → root has
  `class="mt-4"` only (same for `style`); a non-colliding inline attr is added
  alongside.
- **Single-root invariant:** template with two top-level elements → error;
  text-only template → error; conditional single root (`{% if %}<a>{% else
  %}<button>{% endif %}`) → passes.
- **Void root:** a component whose root is `<input/>` validates as one root and
  receives injected attrs.
- **No extras:** component with no inline attrs renders byte-identically to before
  (aside from removed `{{ extra_attrs_html }}` tokens), and still validates.
- **Quote safety:** value containing `"` renders with `'` quoting; value containing
  both quote types → error (existing rule).
- **Builtins:** existing builtin render tests still pass after token removal.

## Out of scope

- Fragment/`<>...</>`-style multi-root support (explicitly disallowed).
- Merging (rather than overriding) `class`/`style`.
- Backward compatibility with existing multi-root templates.
