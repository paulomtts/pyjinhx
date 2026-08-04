# PyJinHx

Build reusable, type-safe UI components for template-based web apps in Python.

PyJinHx combines **Pydantic models** with **Jinja2 templates** to give you template discovery, component composition, and asset bundling.

## Features

- **Automatic Template Discovery** - Place templates next to component files, no manual paths needed
- **Composability** - Nest components easily with single components, lists, and dictionaries
- **Asset Bundling** - Automatically collects and bundles `.js` and `.css` files from component directories
- **Type Safety** - Pydantic models provide validation and IDE support

## Choose your depth

PyJinHx layers optional features on top of a small core. You can stop at any tier:

| Tier | You get | Start here |
|------|---------|------------|
| **1 — Components** | `BaseComponent`, templates, assets | [Quick Start](getting-started/quickstart.md) |
| **2 — Web app** | Per-request isolation via `setup(app)` | [Registry guide](guide/registry.md) |
| **3 — Reactive** | HTMX OOB swaps, `@mutates`, `load()` | [Reactivity](reactivity.md) |
| **4 — Full wiring** | `AppContext`, `IntegrationBackend`, cache, invalidation | [Build an App](getting-started/build-an-app.md) |

Details: [Usage tiers](guide/usage-tiers.md).

## Two Ways to Render

Within Tier 1, PyJinHx offers two complementary approaches:

=== "Python-side"

    Instantiate components in Python and call `.render()`:

    ```python
    from components.ui.button import Button

    button = Button(id="submit", text="Submit", variant="primary")
    html = button.render()
    ```

=== "Template-side"

    Register your components root once so PascalCase tags resolve inside templates,
    then render with the free `render()` function:

    ```python
    from pyjinhx import setup, render
    from components.ui.button import Button

    setup(components_root="./components")
    html = render(Button(id="submit", text="Submit", variant="primary"))
    ```

Both of these render to a string, which is what a script or a static-site build wants. In a
**web app** you do neither: call `setup(app)` once and have each route **return** the
component — see [Build an App](getting-started/build-an-app.md).

## Next Steps

- [Installation](getting-started/installation.md) - Install PyJinHx
- [Build an App](getting-started/build-an-app.md) - Step-by-step tutorial with **Why?** panels (recommended for new users)
- [Quick Start](getting-started/quickstart.md) - Minimal first component
- [Guide](guide/components.md) - Feature reference
- [Components](components.md) - Optional `pyjinhx.builtins` package
- [Response composition](api/responses.md) - What a route handler may return, and what pyjinhx makes of it
- [Public API Index](reference/public-api.md) - Every symbol exported from `pyjinhx`
- [Migration guide](migration.md) — breaking changes, version by version
