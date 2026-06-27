# Loading states

Seven loading niches, one decision rule: *what is missing?*

| What's missing | Builtin | Activation |
|---|---|---|
| Content not loaded yet | `PJXSkeleton` | None — it IS the placeholder; the swap replaces it (`PJXLazyLoad(content=PJXSkeleton())`) |
| Lazy load failed | `PJXLazyLoad` error path | Automatic — on the element's own terminal failure (non-2xx/timeout/network) the placeholder is replaced by its `error` slot, or a default `role="alert"` message (`error_text`); no retry is issued |
| Reactive region refreshing | *runtime state* (`data-pjx-loading`) | Automatic — add `data-pjx-loading="skeleton"` or `data-pjx-loading="spinner"` directly in the `ReactiveComponent` template (on the root element or an inner element); the `pjx.js` runtime shimmer-skeletonizes or overlays the EXISTING content while predicted mutations are in flight |
| Request in flight, inline | `PJXSpinner` | `PJXSpinner(class_name="htmx-indicator")` + `hx-indicator="#its-id"` — htmx toggles it, zero JS |
| Request in flight, region-blocking | `PJXRegionLoader` | `hx-indicator` pointing at it, **or** `pjx.loader.region.show/hide/reset(id)` for non-htmx work (pick one mechanism per element), or `pjx.loader.region.wrap(id, promise)` |
| Request in flight, page navigation | `PJXPageLoader` | Automatic: htmx lifecycle events for GETs targeting `nav_targets`, plus any request from inside `[data-pjx-loader]`; `pjx.loader.page.wrap(promise)` for manual async |
| Determinate progress | `PJXProgress` | `value`/`max` props |

**PJXSkeleton component vs skeleton state.** The `PJXSkeleton` *component* is placeholder DOM for
content that doesn't exist yet (first paint, `PJXLazyLoad` placeholders). The runtime's
`pjx-loading--skeleton` *state* shimmer-masks content that already exists while it refreshes.
Same look, different jobs — and different theming tokens (the component's `--pjx-skeleton-bg`/`--pjx-skeleton-shine` vs the runtime's `--pjx-skeleton-color`/`--pjx-skeleton-highlight`).

```html
<!-- inline: search box with a spinner -->
<input hx-get="/search" hx-trigger="keyup changed delay:300ms" hx-indicator="#search-spin">
<PJXSpinner id="search-spin" class_name="htmx-indicator"/>

<!-- region: a card that blocks while refreshing -->
<div hx-get="/stats" hx-trigger="every 60s" hx-indicator="#stats-overlay">
  <PJXRegionLoader id="stats-overlay"/>
  ...
</div>
```

`htmx-request` is htmx's own class; without htmx these indicators simply stay hidden.

## Concurrency

Overlapping or back-to-back triggers from independent sources are safe across the family —
but the state lives in different places by design:

| Component | Who tracks overlapping triggers |
|---|---|
| `PJXRegionLoader` | its own per-id ref-count: visible from the first `show(id)` to the last `hide(id)`; a show during an in-flight hide cancels it silently; `wrap(id, promise)` pairs the calls for you; nodes replaced mid-flight are re-lit after htmx settles |
| `PJXPageLoader` | its own request ref-count across all tracked htmx requests (plus `pjx.loader.page.wrap`) |
| `PJXSpinner` (as `hx-indicator`) | **htmx itself** — htmx keeps a per-indicator request count and only removes `htmx-request` when the last overlapping request settles |
| `PJXSkeleton` | nobody — it's inert placeholder markup (the *runtime skeleton state* is a different thing: the pjx.js runtime ref-counts it per region and re-lights replaced nodes after swaps) |
| *runtime loading states* (`data-pjx-loading`) | the `pjx.js` runtime — per-region ref-count keyed to each request's `loadend` (fires on load/error/abort, even for superseded responses); regions replaced mid-flight are re-lit after settle |
| `PJXProgress` | the server — concurrent updates are last-write-wins value swaps |

The atoms deliberately hold no client state: adding ref-counts to them would double-manage
what htmx or the server already owns.

!!! note "Singletons"
    `PJXToastHost` and `PJXPageLoader` are mounted **once in your layout**. `PJXPageLoader`'s
    `active_on_load` state clears on full page loads — don't deliver one via a fragment swap.
