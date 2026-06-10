# Loading states

Five loading niches, one decision rule: *what is missing?*

| What's missing | Builtin | Activation |
|---|---|---|
| Content not loaded yet | `Skeleton` | None — it IS the placeholder; the swap replaces it (`LazyPanel(content=Skeleton())`) |
| Request in flight, inline | `Spinner` | `Spinner(class_name="htmx-indicator")` + `hx-indicator="#its-id"` — htmx toggles it, zero JS |
| Request in flight, region-blocking | `RegionLoader` | `hx-indicator` pointing at it, **or** `px.loader.region.show/hide/reset(id)` for non-htmx work (pick one mechanism per element) |
| Request in flight, page navigation | `PageLoader` | Automatic: htmx lifecycle events for GETs targeting `nav_targets`, plus any request from inside `[data-px-loader]`; `px.loader.page.wrap(promise)` for manual async |
| Determinate progress | `Progress` | `value`/`max` props |

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

!!! note "Singletons"
    `ToastHost` and `PageLoader` are mounted **once in your layout**. `PageLoader`'s
    `active_on_load` state clears on full page loads — don't deliver one via a fragment swap.
