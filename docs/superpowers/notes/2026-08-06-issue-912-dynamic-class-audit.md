# Audit: dynamic-class per-instance annotation drift (#912)

**Conclusion:** No per-instance-varying-annotation dynamic-class pattern exists in pyjinhx. Subtask #913 may cache `_is_json_coercible_annotation()` results unscoped, keyed per (class, field), with no exclusions.

## Method

Read-only audit, no source or test changes.

1. Grepped `pyjinhx/` for dynamic class construction and annotation mutation: `create_model`, `types.new_class`, `type("...")`, `__annotations__`, `model_fields =`, `model_fields[`.
2. Grepped for post-hoc mutation specifically: `.__annotations__ =`, `.model_fields =`, `setattr(..., "__annotations__", ...)`, `model_rebuild(`.
3. Traced every dynamic-class site to its call sites to establish whether the class object is built once and reused, or rebuilt/mutated per instance.
4. Cross-checked against the v2 architecture invariant on per-class derived facts.

## Sites found

- `pyjinhx/props_header.py:118-147` — `build_component_class()`, the only `pydantic.create_model` factory, builds a classless-template component class from a parsed `{#def#}` header off base `_OpenComponent`. It sets `cls._pjx_classless` as a plain class attribute after creation, not as an annotation.
- `pyjinhx/classless.py:81-94` — `_placeholder_class()`, a `types.new_class` fallback for templates with no header. It declares no fields at all, so it has no per-field annotations to drift; it likewise sets `_pjx_classless` / `_pjx_template` as plain class attributes.
- `pyjinhx/reactive/component.py:175-190` — reads `__annotations__` (via `get_type_hints`, with a `getattr` fallback) to discover PjxKey fields. A read, never a write.
- `pyjinhx/rendering.py:137` — reads `cls.model_fields[key_field].annotation` off an already-built, already-registered class to validate an incoming key attribute. A read, never a write.

No other `type()`-with-namespace, `types.new_class`, or `create_model` call exists in `pyjinhx/`, and nothing anywhere assigns to `__annotations__` or `model_fields`.

## Call-site trace

Both dynamic-class factories have exactly one call site: `pyjinhx/classless.py:97-134` `component()`.

- It returns `discovery.get_class(tag)` immediately when a class is already registered for the tag.
- Otherwise it takes `_build_lock` and re-checks `discovery.get_class(tag)` — double-checked locking — so at most one class object is ever built per tag per process.
- The freshly built class gets `__module__` set, `rebuild_class_descriptor(cls)` run once, and is then handed to `discovery.register_class(tag, cls)`.
- Every subsequent instantiation of that tag reuses the same registered class object. Annotations are fixed at that single build point and are never re-derived or mutated afterward.

## Cross-check

This matches `docs/superpowers/rebuild/architecture-overview.md` invariant #5 (line 17): per-class derived facts are computed once, at registration, following the `_pjx_children_target` pattern — no per-render recomputation, no scattered cache retrofits. #913's cache should follow the same discipline.

## Consequence for #913 / #914

- #913: unblocked to cache `_is_json_coercible_annotation()` per (class, field) with no carve-outs. `_is_json_coercible_annotation()` (`pyjinhx/_component.py:137-151`) is a pure function of the annotation object; its hot call site is `pyjinhx/_component.py:637`, inside a per-instance loop.
- #914: owns the correctness tests and the `scripts/bench_field_count.py` re-run. Nothing in this audit adds or changes tests.
