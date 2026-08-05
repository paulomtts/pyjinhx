# Responses

`pyjinhx.responses` is the framework-free response layer: what one handler return becomes. Every backend funnels its handler returns through this module and does nothing with the answer but emit it, so no two backends can disagree about fan-out or the htmx header set.

Nothing in this module needs a web framework installed. `compose()` is callable from a test or a script.

!!! note "You do not call this"
    `pyjinhx.responses` is not exported from `pyjinhx` and is not part of the public API.
    In an app wired with `setup(app)`, the adapter runs `compose()` on your handler's
    return — that is the whole contract, and this page describes what it does with each
    shape you might return. Import from here only for tests and custom adapters.

## compose()

```python
def compose(result: object, *, session: RenderSession | None = None) -> object
```

Turn one handler return into a `PjxResponse`, or answer `PASSTHROUGH`.

`session` defaults to the active `request_scope()`'s session, and to a bare `RenderSession()` outside a scope — a session with an empty mounted manifest, which means no OOB legs.

### The four return shapes

| Handler returns | Primary body | Result |
|---|---|---|
| a `BaseComponent` | `render(result, session=session)` | `PjxResponse` |
| `None` | `""` | `PjxResponse` with `HX-Reswap: none` |
| a `str`, `Markup`, or any object with `__html__` | the value verbatim, via `Markup()` | `PjxResponse` |
| anything else | — | `PASSTHROUGH` |

The third row goes through `Markup()` rather than `str()` on purpose: a handler-supplied primary can be an object exposing only `__html__` and never `__str__`, and `Markup` is what adopts that protocol without escaping.

!!! warning "A `str` return never carries the runtime"
    The two body-producing rows are peers to `compose()`, but not to the backend around it. `FastAPIBackend.to_response()` calls `inject_runtime()` only when the return `isinstance(result, BaseComponent)` — every other shape is assumed to be a fragment of a page that already booted. So a *cold page* returned as a `str` or `Markup` ships without pjx.js and without htmx: nothing on that page can issue a pjx request, and fan-out never starts. Return the component for a full-page render; keep the string form for fragments.

`PASSTHROUGH` is how a framework's own response object survives composition untouched — including a redirect, which the backend then gets its own chance to translate (see [Native redirects](#native-redirects)).

!!! note "`None` and `HX-Reswap: none`"
    An OOB-only body has nothing for htmx's default swap to place, so htmx would swap the empty primary into the triggering element and wipe it. `compose()` sets `HX-Reswap: none` whenever the primary is blank, which leaves the trigger alone and lets the OOB fragments land.

## Fan-out is unconditional

Every path that produces a body gets fan-out attached, because the dirtied keys belong to the *request*, not to whatever the handler chose to return: a mutation that dirtied `todos` did so no matter which of the equivalent spellings the author reached for. There is no flag, no backend requirement, and no opt-out.

The composed body is, in order:

1. the primary markup,
2. `oob_swaps(candidates)` — the `outerHTML:` and `delete:` legs for dirty and missing regions,
3. `missing_asset_oob(candidates, session.pjx_assets, session)` — the assets this walk needs and the client reports it lacks.

Empty parts are dropped and the rest joined with newlines.

Before walking, `compose()` calls `invalidate(dirtied)`. Eviction happens before the walk, never after: `walk_manifest()` reads the load cache to decide clean vs dirty, so an entry a dirtied key had already staled would otherwise answer "clean" and the client would keep markup this request just invalidated. `@mutates` and `dirty()` only *record* keys; this is where they are consumed.

The walk is passed `primary_html=primary` so a region the primary body already carries is not also swapped out-of-band — without it the client would swap that region twice in one response.

!!! warning "`render()` does not fan out"
    `render()` returns one component's markup and nothing else. It has never appended OOB swaps, read the mounted manifest, or evicted a cache entry. What is true is that *returning* a component (or a string) from a handler gets fan-out, because the composer attaches it.

    So a mutation route should `return TodoList.load(...)` — or `return None` when it has no primary to show — and let dependents ride along on composition. `return TodoList.load(...).render()` is a plain string primary; it still fans out, but only because `compose()` saw the string, not because `render()` did anything.

## PjxResponse

```python
@dataclass(frozen=True)
class PjxResponse:
    body: str
    headers: dict[str, str]
    status: int = 200
```

One composed response, in terms no web framework has to be installed for. A backend's whole remaining job is turning this into its own response type — the FastAPI adapter builds an `HTMLResponse(body, headers=headers, status_code=status)`.

## PASSTHROUGH

```python
PASSTHROUGH = object()
```

`compose()`'s answer for a return value that is not pyjinhx's to adapt. It is an identity sentinel; test it with `is`, never `==`:

```python
from pyjinhx.responses import PASSTHROUGH, PjxResponse, compose

composed = compose(result, session=session)
if composed is PASSTHROUGH:
    ...  # keep the handler's own value
```

## Native redirects

A redirect response takes the `PASSTHROUGH` path out of `compose()` and is then translated by the backend. htmx follows a 3xx transparently inside XHR and swaps the redirect target's *body* into the triggering element, which is never what the handler meant.

A result is translated when all three hold:

- the request carries `HX-Request: true`,
- `result.status_code` is in `range(300, 400)`,
- `result.headers` has a `Location` (or `location`).

The translation is `Response(status_code=204, headers={"HX-Redirect": location})`, which htmx turns into a full-page navigation.

Detection is duck-typed on that shape, not on `RedirectResponse`, so hand-built and third-party redirect responses translate too. It is always on: there is no pyjinhx `redirect()` helper and no setting. A request that is *not* an htmx request gets the real 3xx untouched, so a plain browser navigation still redirects normally.

```python
from starlette.responses import RedirectResponse


@app.post("/todos")
def create(title: str):
    ...
    return RedirectResponse("/", status_code=303)
    # htmx request  -> 204 + HX-Redirect: /
    # browser POST  -> 303 + Location: / (untouched)
```

### HX-Location

`HX-Location` (htmx's client-side, no-reload navigation) has no pyjinhx surface. Spell it yourself — a non-3xx response is not a redirect by the rule above, so it passes through untouched:

```python
from starlette.responses import Response

return Response(status_code=204, headers={"HX-Location": "/todos"})
```

## See also

- [Reactivity](../reactivity.md) — what makes a region a fan-out candidate.
- [Cache & Invalidation](cache-invalidation.md) — `invalidate()`, `walk_manifest()`, `oob_swaps()`.
- [Integration Backend](client-backend.md) — the `to_response()` contract a backend implements around `compose()`.
