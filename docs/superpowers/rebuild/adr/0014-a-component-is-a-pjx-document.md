# ADR 0014: A component is a pjx document, optionally owned by a class

**Status:** Proposed (draft), 2026-11-25. Supersedes [ADR 0008](./0008-drop-sfc-python-blocks.md); extends [ADR 0007](./0007-single-template-convention.md).

## Context

ADR 0008 dropped v0.x's single-file components — a `{# python #}` block inside a `.pjx` file — and left the door open: "if demand resurfaces, a new ADR reverses this with fresh context."

Demand resurfaced, with numbers. A consumer app has 382 components spread over `.py` + `.pjx` + `.css` + `.js`. Of its 275 component classes, 183 must remain classes (reactive, classmethod factories, properties, validators) and 91 exist only because a `{#def#}` header cannot express their fields. It also carries 211 sibling `.css` and 56 sibling `.js` files, many a few lines long.

The fresh context is that 0008 rejected a *container*, not the goal. Every objection it raised follows from putting Python inside a template file. None of them applies to putting the template inside a Python file, or to letting a template say more about itself.

## Options

For the class that must stay a class:

1. **`.pjx` host with a `{# python #}` block and an import hook** — the v0.x design, hardened.
2. **`.pjx` host with a generated shadow `.py`** — no hook, but a mandatory generation step and a derived second copy of the code.
3. **`.py` host with an inline template** — the class carries `template = """…"""`; pyjinhx reads the string back from the module's source with `ast`.

Comparison: `docs/superpowers/specs/2026-11-25-sfc-v2-candidates.md`. Full design: `docs/superpowers/specs/2026-11-25-fewer-files-design.md`.

## Decision

One model: **a component is a pjx document, optionally owned by a Python class.**

A pjx document is markup plus up to three Jinja-comment blocks — `{#def … #}` (props), `{#css … #}`, `{#js … #}`. It lives either in a `.pjx` file or in the `template` string literal of the class that owns it (option 3), and means the same thing in both places.

Three decisions follow from that model:

1. **A class may hold its document.** The existing MRO template walk checks each ancestor for an inline `template` before probing for its file. The module is ordinary Python; the string is recovered by `ast.parse`, lazily, and line-padded so template line numbers equal `.py` line numbers.
2. **The `{#def#}` header says more.** `Literal`, generics, real unions, `ExtraAttrs`/`AttrValue`; a required `id` means `auto_id = False`; and a *dotted name* is an import path — a type, a constant default, or with `()` a default factory.
3. **A header-only template answers its tag.** Discovery records unclaimed `.pjx` stems; on a tag miss the classless factory builds the class if that file carries a `{#def#}` header. Lazy, header-gated, no `component()` call required.

Inline `{#css#}` / `{#js#}` blocks are a separate change; this ADR fixes only the rule that makes them compose: template source is read through one function, never `template_path.read_text()`.

### ADR 0008's objections, one by one

**"Requires extracting and exec-ing embedded Python at discovery time."**
Nothing is exec-ed by pyjinhx. A component module is imported by Python's own import system, the way every class-based component already is. The template is recovered by parsing the module's source — a read, not an execution — at first render, not at discovery. Discovery opens no `.py` file. 0008's consequence "no exec of template-embedded Python anywhere in v2 discovery" continues to hold verbatim.

The dotted-name rule in headers deserves the same scrutiny. It compiles and runs nothing from the template: a declarative reference is handed to `pkgutil.resolve_name`, which imports a module the application already ships. It happens when the component is first built, not at discovery.

**"Couples template parsing to Python tooling — type-checking, LSP."**
The coupling is inverted and mostly dissolved. Python tooling sees a plain `.py` file: no stubs, no `extraPaths`, no stub-freshness check in CI; rename and go-to-definition act on the real code. What needs help now is the template inside a string, and that help is an editor grammar injection — optional, cosmetic when absent, unable to fail a build. pjx-ls never has to front a Python language service.

**"Import semantics for code that lives in a non-`.py` file" / opaque code placement.**
There is no such code. `__file__`, `__module__`, tracebacks, breakpoints, coverage and `inspect.getsource` behave as for any module. No `sys.meta_path` finder is installed and no `.py`-versus-`.pjx` collision can arise.

**"A fourth shape … doesn't pay for itself."**
No shape is added. 0008 listed three: class + adjacent template, classless `component()`, `{#def#}`-headed template. The first gains a second place its template may live; the second and third merge, because a headed template now registers itself. Resolution, the registry, slots, strictness, caching and asset walking are unchanged.

### What it costs

- Markup inside a Python string has no highlighting or template diagnostics until an editor injection is installed.
- Templates with backslashes need raw strings; templates containing `"""` need `'''`.
- A template-only edit touches a `.py` file, so `*.py`-watching dev reloaders restart where a `.pjx` edit would not.
- `template` becomes a reserved class-level name on components.
- A header can now trigger an import. A wrong dotted path fails when the component is first built, not at startup.
- A headed orphan template whose tag was previously passing through as literal markup now renders as a component. That is the intent, and it is a behaviour change.

## Consequences

- `BaseComponent` gains `template: ClassVar[str | None]`; `ClassDescriptor` gains `inline_class`; `template_path` may name a `.py` file.
- Code that needs a template's source goes through `sfc.read_document(template_path, inline_class)`. The Jinja loader, the inline-block scanner, `InlineAsset` and the stale-header probe are its only callers.
- Template line numbers equal `.py` line numbers by construction, so errors — and a future pjx-ls embedding — need no source map.
- `.py` + `.pjx` (+ `.css` / `.js`) remains fully supported. Migration is per component and reversible; a fold script is provided for the mechanical cases.
- ADR 0007 is extended, not broken: the on-disk convention is still `.pjx` + snake_case; an inline template is consulted before the probe and costs no probe.
- v0.x `{# python #}` files remain unsupported and still migrate by splitting — now optionally into one file instead of two.
