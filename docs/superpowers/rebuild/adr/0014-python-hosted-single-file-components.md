# ADR 0014: Single-file components are Python modules with an inline template

**Status:** Proposed (draft), 2026-11-25. Supersedes [ADR 0008](./0008-drop-sfc-python-blocks.md).

## Context

ADR 0008 dropped v0.x's single-file components — a `{# python #}` block inside a `.pjx` file — and left the door open: "if demand resurfaces, a new ADR reverses this with fresh context."

Demand resurfaced. A consumer app with hundreds of components carries each one as `.py` + `.pjx` + `.css` + `.js`, and the four-way split is now its main maintenance cost. Inline `{# css #}` / `{# js #}` blocks and `{#def#}` classless templates (separate work) collapse the split for components with no Python logic. Components that need a class still span at least two files.

The fresh context is that 0008 rejected a *container*, not the goal. Every objection it raised follows from putting Python inside a template file. Putting the template inside a Python file has none of them.

## Options

1. **`.pjx` host with a `{# python #}` block and an import hook** — the v0.x design, hardened.
2. **`.pjx` host with a generated shadow `.py`** — no hook, but a mandatory generation step and a second, derived copy of the code.
3. **`.py` host with an inline template** — the class carries `template = """…"""`; pyjinhx reads the string back from the module's source with `ast`.

Full comparison: `docs/superpowers/specs/2026-11-25-sfc-v2-design.md`.

## Decision

Option 3. A component class may declare its template as a string literal class attribute instead of an adjacent `.pjx` file:

```python
class Counter(BaseComponent):
    remaining: int = 0

    template = """
    <div class="counter">{{ remaining }} left</div>
    """
```

The string is a pjx document, equivalent in every respect to the file it replaces. The existing MRO template walk checks each ancestor for an inline template before probing for its file.

### ADR 0008's objections, one by one

**"Requires extracting and exec-ing embedded Python at discovery time."**
Nothing is exec-ed by pyjinhx. The component module is imported by Python's own import system, the way every class-based component already is. The template is recovered by `ast.parse` over the module's source file — a read, not an execution — and that happens lazily at first render, not at discovery. Discovery does not open `.py` files at all. 0008's consequence "no exec of template-embedded Python anywhere in v2 discovery" continues to hold, verbatim.

**"Couples template parsing to Python tooling — type-checking, LSP."**
The coupling is inverted and mostly dissolved. Python tooling sees a plain `.py` file: no stubs, no `extraPaths`, no stub-freshness check in CI, and rename/go-to-definition operate on the real code. What needs help now is the *template* inside a string, and that help is an editor grammar injection — optional, cosmetic when absent, and unable to fail a build. pjx-ls never has to host a Python language service.

**"Import semantics for code that lives in a non-`.py` file" / opaque code placement.**
There is no such code. `__file__`, `__module__`, tracebacks, breakpoints, coverage and `inspect.getsource` all behave as for any module. No `sys.meta_path` finder is installed and no `.py`-versus-`.pjx` name collision can arise.

**"A fourth shape … doesn't pay for itself."**
This is not a fourth shape. It is the first shape (class + template) with one more place the template may live. The registry, slots, strictness, caching, asset resolution and inheritance are unchanged; the implementation is one `ast` lookup, one branch in the template walk, one descriptor field and a few lines in the loader.

### What it costs

- Markup inside a Python string has no highlighting or template diagnostics until an editor injection is installed.
- Templates containing backslashes must use raw strings; templates containing `"""` must use `'''`.
- A template-only edit touches a `.py` file, so `*.py`-watching dev reloaders restart the process where a `.pjx` edit would not.
- `template` becomes a reserved class-level name on components.

## Consequences

- `BaseComponent` gains `template: ClassVar[str | None]`; `ClassDescriptor` gains `inline_class`.
- `template_path` may now name a `.py` file. Code that needs a template's *source* must go through the loader or `sfc.extract_template`, never `template_path.read_text()`. The inline css/js block work is the first consumer of that rule.
- Template line numbers equal `.py` line numbers by construction (comment padding), so errors and future pjx-ls embedding need no source map.
- `.py` + `.pjx` remains fully supported; migration is per class and reversible. A `fold` / `unfold` codemod is specified, not yet built.
- ADR 0007 (one template convention) is extended, not broken: the on-disk convention is still `.pjx` + snake_case; an inline template is consulted before the probe and costs no probe.
- v0.x `{# python #}` files are still not supported and still migrate by splitting — now optionally into one file instead of two.
