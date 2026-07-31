# ADR 0003: Slots are opaque — truthiness, interpolation, and `.props` access only

**Status:** Accepted, 2026-07-28. Amended 2026-07-30 to sanction `NestedComponentWrapper`. Consequence of ADR 0002.

## Context

Under v0.36's string model, a slot value is a genuine string during `template.render()`, so `{{ content|length }}`, `content in x`, and `{{ content|striptags }}` all work — this is precisely why v0.36 opacifies the *output* rather than the *context*, at real complexity cost. Under ADR 0002, child output is an opaque node; a slot holding a component cannot be a plain string without re-flattening structure.

## Options

1. **Opaque + truthiness only.** Templates may test `{% if content %}` and interpolate `{{ content }}`. String filters on component slots raise with a clear error naming the slot and the fix.
2. **Lazy stringify.** Opaque node implements `__str__`/`__len__`, forcing early child render when inspected. Filters keep working; hidden eager rendering reintroduces string-model complexity into layer 0 and makes render order data-dependent.
3. **Survey-then-decide.** Defer until slot-filter usage in builtins/docs is measured.

## Decision

Option 1, with option 3's survey folded in as a pre-RFC-1 gate (PRD risk 1): grep builtins and docs for string operations on slot values before layer 1's RFC. If usage turns out widespread, this ADR gets revisited *before* L1 — not discovered after.

String-valued slots (a `Slot` field assigned a plain string) are unaffected — they remain raw-HTML-capable strings. This ADR governs slots holding rendered components.

## Consequences

- Child opacity stays absolute; no hidden render forcing; layer 0 stays simple.
- `{% if content %}`, `{{ content }}` work; `{{ content|length }}` on a component slot raises a targeted error instead of silently misbehaving.
- Migration note required for any v0.x template using string filters over component slots (expected rare; verified by the survey).

## Amendment (2026-07-30): `NestedComponentWrapper`

L1.3 (roadmap item 3) calls for `{{ field.props.x }}` alongside bare `{{ field }}` — reading a nested child's *validated field values* from the parent template, without breaking opacity. This is narrower than general attribute delegation: the wrapper exposes exactly `.props` (a read-only view over the child component's own fields, not arbitrary Python attributes/methods), plus interpolation and truthiness. It does not expose `__str__`/`__len__`/iteration or any other implicit stringification hook — those still raise the ADR's targeted opacity error. This keeps the "no hidden render forcing" guarantee: reading `.props.x` touches the child's *already-validated* field data, not its rendered output.

## Survey outcome (2026-07-30)

L0.G ran the pre-RFC-1 survey this ADR calls for, split across three gate subtasks:

- **#293** (grep builtins) and **#294** (grep docs+demos) searched every built-in
  component and every documented/demo template for string filters (`|length`,
  `|striptags`, `|trim`, ...), slicing, `in` membership, and comparisons applied
  to a slot-typed variable. **Zero matches** anywhere in the codebase or docs.
- **#295** classified the result as "nothing to classify": the rare/nonexistent
  usage condition from Option 3 is confirmed, so this ADR does not need
  revisiting before L1 — the decision (Option 1, opaque + truthiness/interpolation
  only) stands as written above.
- **#296** (this entry) designs the concrete error contract L1 must implement,
  since "zero usages today" doesn't remove the need for the error the ADR
  promised — it only means no existing template will trip it.

### Error contract for L1

`ComponentNode` (`pyjinhx2/markers.py`) currently exposes only `__repr__`; it has
no `__bool__`, `__str__`, `__len__`, `__iter__`, or comparison dunders. L1 is
expected to add the two capabilities this ADR grants — truthiness and
interpolation — and nothing else. Any other operation must fail fast with a
`TypeError` rather than falling through to `object`'s defaults (which would
silently succeed with meaningless results, e.g. `__bool__` defaulting to
`True`, `__len__` raising `AttributeError` instead of a targeted message).

Message format (matches the `{ClassName} (template: {path}): ...` prefix
convention from `render.py`'s `render_level`, and the "name the class, name the
problem, name the fix" shape of `component.py`'s `_missing_template_error`):

```
{ComponentClassName} (template: {template_path}): slot '{field_name}' holds a
rendered component, so `{operation}` is not supported on it. Component slots
are opaque outside `{% if %}` and `{{ }}`: use `{% if {field_name} %}` to test
for presence, or `{{ {field_name} }}` to render it directly. String filters,
slicing, membership tests, and comparisons are not available on component
slots.
```

Concrete example, for a `{{ content|length }}` use on `Card.content`:

```
Card (template: card.pjx): slot 'content' holds a rendered component, so
`|length` is not supported on it. Component slots are opaque outside `{% if %}`
and `{{ }}`: use `{% if content %}` to test for presence, or `{{ content }}` to
render it directly. String filters, slicing, membership tests, and comparisons
are not available on component slots.
```

`{operation}` is filled in with the literal syntax attempted (`|length`,
`|striptags`, `[0:3]`, `in`, `==`, etc.) so the message reads like a diff of
what the author wrote, not a generic category name. This is raised as a
`TypeError` at render time, from the dunder L1 wires up for that operation
(`__len__`, `__getitem__`, `__contains__`, `__eq__`, ...) — not a Jinja-layer
check, so it fires regardless of how the template reaches the operation.

### Migration note (pyjinhx v1 → v2)

This is a behavior change, and it is rare: the L0.G survey found no existing
usage of string filters, slicing, membership, or comparisons on
component-valued slots anywhere in this codebase's builtins or docs. Most v1
templates will be unaffected.

If you do hit it after upgrading: a v1 template applied a string-style
operation (a filter like `|length`/`|striptags`/`|trim`, slicing, `in`, or a
comparison) to a `Slot` field that holds a rendered child component rather
than a plain string. In v2 that field is an opaque node, not a string — only
`{% if field %}` (presence) and `{{ field }}` (rendering) are supported. Fix
the template to use one of those two forms instead; if you need the child's
*text content* (e.g. for a length check), read it from the underlying data
your component passed into the slot, before it becomes a rendered component —
not by inspecting the rendered slot after the fact.
