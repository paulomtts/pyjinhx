# Loading states

Six loading niches, one decision rule: *what is missing?*

| What's missing | Builtin | Activation |
|---|---|---|
| Content not loaded yet | `Skeleton` | None — it IS the placeholder; the swap replaces it (`LazyPanel(content=Skeleton())`) |
| Reactive region refreshing | *runtime state* (`data-pjx-loading`) | Automatic — add `data-pjx-loading="skeleton"` or `data-pjx-loading="spinner"` directly in the `ReactiveComponent` template (on the root element or an inner element); the `pjx.js` runtime shimmer-skeletonizes or overlays the EXISTING content while predicted mutations are in flight |
| Request in flight, inline | `Spinner` | `Spinner(class_name="htmx-indicator")` + `hx-indicator="#its-id"` — htmx toggles it, zero JS |
| Request in flight, region-blocking | `RegionLoader` | `hx-indicator` pointing at it, **or** `px.loader.region.show/hide/reset(id)` for non-htmx work (pick one mechanism per element), or `px.loader.region.wrap(id, promise)` |
| Request in flight, page navigation | `PageLoader` | Automatic: htmx lifecycle events for GETs targeting `nav_targets`, plus any request from inside `[data-px-loader]`; `px.loader.page.wrap(promise)` for manual async |
| Determinate progress | `Progress` | `value`/`max` props |

**Skeleton component vs skeleton state.** The `Skeleton` *component* is placeholder DOM for
content that doesn't exist yet (first paint, `LazyPanel` placeholders). The runtime's
`pjx-loading--skeleton` *state* shimmer-masks content that already exists while it refreshes.
Same look, different jobs — and different theming tokens (`--px-skeleton-*` vs `--pjx-skeleton-*`).

```html
<!-- inline: search box with a spinner -->
<input hx-get="/search" hx-trigger="keyup changed delay:300ms" hx-indicator="#search-spin">
<Spinner id="search-spin" class_name="htmx-indicator"/>

<!-- region: a card that blocks while refreshing -->
<div hx-get="/stats" hx-trigger="every 60s" hx-indicator="#stats-overlay">
  <RegionLoader id="stats-overlay"/>
  ...
</div>
```

`htmx-request` is htmx's own class; without htmx these indicators simply stay hidden.

## Concurrency

Overlapping or back-to-back triggers from independent sources are safe across the family —
but the state lives in different places by design:

| Component | Who tracks overlapping triggers |
|---|---|
| `RegionLoader` | its own per-id ref-count: visible from the first `show(id)` to the last `hide(id)`; a show during an in-flight hide cancels it silently; `wrap(id, promise)` pairs the calls for you; nodes replaced mid-flight are re-lit after htmx settles |
| `PageLoader` | its own request ref-count across all tracked htmx requests (plus `px.loader.page.wrap`) |
| `Spinner` (as `hx-indicator`) | **htmx itself** — htmx keeps a per-indicator request count and only removes `htmx-request` when the last overlapping request settles |
| `Skeleton` | nobody — it's inert placeholder markup (the *runtime skeleton state* is a different thing: the pjx.js runtime ref-counts it per region and re-lights replaced nodes after swaps) |
| *runtime loading states* (`data-pjx-loading`) | the `pjx.js` runtime — per-region ref-count keyed to each request's `loadend` (fires on load/error/abort, even for superseded responses); regions replaced mid-flight are re-lit after settle |
| `Progress` | the server — concurrent updates are last-write-wins value swaps |

The atoms deliberately hold no client state: adding ref-counts to them would double-manage
what htmx or the server already owns.

!!! note "Singletons"
    `ToastHost` and `PageLoader` are mounted **once in your layout**. `PageLoader`'s
    `active_on_load` state clears on full page loads — don't deliver one via a fragment swap.
