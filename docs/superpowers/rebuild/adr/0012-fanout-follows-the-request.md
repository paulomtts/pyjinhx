# ADR 0012: Fan-out follows the request, not the return value

**Status:** Accepted, 2026-08-04. Depends on ADR 0001 and ADR 0009. Supersedes the response-object half of the #475 redirect decision.

## Context

OOB fan-out — rebuilding every mounted region a request's dirtied keys invalidated — had exactly one caller in the codebase: `ReactiveResponse.body`. A handler got fan-out only by remembering to return `ReactiveResponse(primary=..., mounted=request)`. Returning the component itself produced its markup and nothing else.

Two consequences followed, and both were live defects.

`docs/reactivity.md` claimed that any component's `.render()` appends OOB swaps, and gave `return ReportSummary(report=report).render()` as the example. That line shipped zero OOB fragments. The documented behaviour did not exist anywhere in the implementation.

More seriously, forgetting the wrapper was silent. The mutation still recorded its dirtied keys; the counters and totals simply never refreshed, and nothing on either side of the wire reported a problem.

The root cause is a category error: **fan-out was attached to a return type when it is a property of the request.** `store.add()` dirtied `todos` regardless of which of two equivalent spellings the handler reached for. Whether the rest of the page refreshes should not depend on that choice.

A third problem sat in the same object. `ReactiveResponse` carried `redirect=`/`redirect_mode=` because htmx never sees a 3xx — the browser's fetch follows it transparently and hands htmx the whole destination document, which then lands in whatever fragment slot the trigger targeted. v0.x fixed this by translating `3xx → 204 + HX-Redirect` in middleware, gated behind `setup(htmx_redirects=True)`. The v2 port split that into two subtasks: #475 carried the intent on `ReactiveResponse`, #449 was to do the translation in the integration. #475 shipped and #449 never did, leaving redirect intent parked on an object whose every other field (`primary`, `mounted`, `assets`) is meaningless in the redirect case.

Composition also could not move without a second change. `ReactiveResponse` read the client's manifest from a Starlette request, so any framework-agnostic composer would have needed a request-shaped object handed to it — making "framework-agnostic" a naming convention rather than a fact.

## Options

1. **Make `.render()` do fan-out** — matches the docs literally. Rejected: `.render()` is a pure "give me this component's HTML" call used in nested and non-HTTP contexts, and attaching request-scoped side effects to it would make the same call mean different things depending on where it ran.
2. **Keep the wrapper, document it harder** — cheapest. Rejected: the failure mode is silence. No amount of documentation makes a forgotten wrapper visible at the point it goes wrong.
3. **Auto-wrap in the FastAPI adapter** — smallest code change that fixes the defect. Rejected as the whole answer: every future backend would reimplement the fan-out ordering and dedupe rules, and would get them subtly wrong.
4. **Compose in a framework-free core, always fan out** — one `compose()` decides what a handler return becomes; backends only emit. Chosen.

## Decision

Option 4, in four parts.

**The parsed pjx manifests live on `RenderSession`.** `pjx_mounted`, `pjx_assets` and `pjx_trigger` are filled by the backend's middleware before the handler runs. This is the load-bearing part: it is what allows composition to touch no framework object at all.

**`compose(result, *, session=None)` in `pyjinhx/responses.py` owns composition**, and imports no web framework. A `BaseComponent` renders as the primary; `None` is an empty primary; a `str`, `Markup` or anything exposing `__html__` is taken as markup; anything else answers the `PASSTHROUGH` sentinel. On every path that produces a body, fan-out is attached — there is no branch that yields markup and skips it. It returns `PjxResponse(body, headers, status)`.

**`ReactiveResponse` is removed outright, with no replacement export.** Not deprecated: v2 has not had a 1.0 release, and keeping both spellings alive preserves the exact ambiguity this decision exists to end.

**pyjinhx owns no redirect surface.** A `redirect()` helper was designed and dropped. Pushing a URL is the framework's job; all pyjinhx owes anyone is stopping htmx from swallowing the framework's own redirect. The backend translates a native 3xx into `204 + HX-Redirect`, gated on the `HX-Request` header and detected by shape (`status_code` in 300–399 plus a `Location` header) rather than by class. This closes #449 and supersedes #475.

Making fan-out unconditional is safe because every anti-double-swap guard already exists inside `walk_manifest` and none of them changes: `_mounted_ids_in(primary_html)` excludes regions the primary already carries, `_drop_nested` drops regions inside another survivor's region (ADR 0001's outerHTML-only swaps make a parent's swap already carry its children), and `_hash_gate_drops` drops regions whose output did not move (ADR 0009 E12). The full-page cold-render case self-neutralises: no `X-PJX-Mounted` header means an empty manifest means zero candidates.

## Consequences

- A handler returning a bare component after a mutation now fans out. Routes lose their `request` parameter, their `.render()` call and their wrapper:

  ```python
  @app.post("/todos")
  def add_todo(text: str = Form(...)):
      todo = store.add(text)
      return ItemRow(todo_id=todo.id, id=f"row-{todo.id}")
  ```

- **Breaking.** `ReactiveResponse` no longer exists. `ReactiveResponse(primary=c.render(), mounted=request)` becomes `return c`; `ReactiveResponse(mounted=request)` becomes `return None`; `ReactiveResponse(..., redirect="/x")` becomes the framework's own `RedirectResponse("/x")`.
- A backend's obligations reduce to four mechanical steps: open `request_scope`, fill the three session fields, call `compose`, emit — plus, optionally, the native-redirect translation. Nothing about fan-out ordering, dedupe or htmx header names is reimplementable per backend, so two backends cannot drift apart on any of it.
- Composition is testable with no web framework installed. `compose(result, session=...)` takes an explicit session, so a unit test drives fan-out from a hand-written manifest.
- `.render()` is unchanged and still returns one component's markup and nothing else. The docs' original claim stays false; what becomes true is the weaker statement that *returning* a component gets fan-out, because the composer attaches it.
- `HX-Location` (htmx's client-side ajax navigation) has no status-code spelling and therefore no translation. A caller asks for it by returning a plain `Response(status_code=204, headers={"HX-Location": ...})`, which reaches the wire through `PASSTHROUGH` untouched. Judged not worth a public surface.
- `PjxContext.mounted`/`.assets`/`.trigger` read the session rather than `request.state`. Strictly more robust: they previously answered `None` whenever the scope was entered without a Starlette request.
- Redirect translation is always on, with no `PjxSettings` gate — unlike v0.x's opt-in `htmx_redirects=True`. An opt-in flag for "do not be broken" is a flag nobody should have to find. Non-htmx requests are untouched, so a plain browser navigation still receives a real 3xx.
- This decision changes *where fan-out is triggered from*, not whether it resolves against a live client. `data-pjx-type`/`data-pjx-load` are still unstamped server-side (#446), so a real client-built manifest carries empty fields and the walk filters everything out. That remains open.
