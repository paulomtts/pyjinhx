# Components

The built-in `pyjinhx.builtins` components, rendered here at docs build time. Each shows a live render and its PascalCase HTML; expand the accordions for props, style tokens, the DOM contract, and the Python form. Import them from `pyjinhx.builtins` (see the [API index](reference/public-api.md)). `PJXLazyLoad` needs a backend, so it has no live render.

**Conventions:** Markup classes use the **`pjx-`** prefix; overrides use **`--pjx-`** custom properties. Builtin CSS also references **theme variables** (`--surface`, `--border`, `--text`, `--radius-md`, `--shadow-md`, `--transition`, `--brand`, …)—define those in your global CSS or map them to your design system. See [builtin-conventions.md](guide/builtin-conventions.md) for the full per-component contract (auto-id, `class_name`, `extra_attrs`, `js`/`css`, headless IIFE JS under `window.pjx`, cancelable `pjx:*:before-*` events). Every component inherits `id`, `js`/`css`, `class_name`, `extra_attrs`, `render()`, and `__html__()` from [BaseComponent](api/base-component.md); `id` is omitted from the props tables below.

**Children-vs-`content` tag gotcha (children-mapping components):** Several components map children to a single attribute (e.g. PJXNotification `content`, PJXTooltip `content`). If you use `Renderer.render()` with PascalCase tags, do **not** supply both child text and the corresponding attribute on the same tag—use body text as the child *or* the attribute, not both.

**Backdrop click (PJXModal and PJXDrawer):** Both render a native `<dialog>`; a document `click` listener treats a click whose target is the `<dialog>` root itself (the backdrop) as a close. Any native `<dialog>` clicked directly is affected—use unique ids and avoid stacking multiple dialogs unless you adjust this.

## Static

### PJXBadge

Small status label. **Assets:** `pjx_badge.css` only.

<!-- demo: PJXBadge -->

```html
<PJXBadge label="Active" color="brand"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `label` | `str` | `""` | Inner text. |
    | `color` | literal | `"neutral"` | `brand`, `error`, `neutral`, `muted` → `pjx-badge--{color}`. |
    | `shape` | literal | `"md"` | `square`, `sm`, `md`, `full` → `pjx-badge--{shape}`. |

??? note "Style tokens"

    | Token | Default (maps to) |
    | --- | --- |
    | `--pjx-badge-font-size` | `var(--font-size-xs)` |
    | `--pjx-badge-radius-sm` | `var(--radius-sm)` |
    | `--pjx-badge-radius-md` | `var(--radius-md)` |
    | `--pjx-badge-radius-full` | `var(--radius-full)` |
    | `--pjx-badge-brand-bg` | `var(--brand-subtle)` |
    | `--pjx-badge-brand-fg` | `var(--brand-muted)` |
    | `--pjx-badge-brand-accent` | `var(--brand)` |
    | `--pjx-badge-error-bg` | `var(--error-bg)` |
    | `--pjx-badge-error-fg` | `var(--error)` |
    | `--pjx-badge-error-border` | `var(--error-border)` |
    | `--pjx-badge-neutral-bg` | `var(--surface-alt)` |
    | `--pjx-badge-neutral-fg` | `var(--text)` |
    | `--pjx-badge-neutral-border` | `var(--border)` |
    | `--pjx-badge-muted-bg` | `var(--surface)` |
    | `--pjx-badge-muted-fg` | `var(--text-muted)` |
    | `--pjx-badge-muted-border` | `var(--border)` |

??? note "DOM & classes"

    Root `.pjx-badge`; no JS API.

    **Classes:** `pjx-badge`; color modifiers `pjx-badge--brand`, `--error`, `--neutral`, `--muted`; shape `pjx-badge--square`, `--sm`, `--md`, `--full`.

??? note "Python"

    ```python
    PJXBadge(label="Active", color="brand")
    ```

### PJXCard

`<article>` shell for composed card layouts. Compose with `PJXCardHeader`, `PJXCardBody`, and `PJXCardFooter` parts. **Assets:** `pjx-card.css` only.

<!-- demo: PJXCard -->

```html
<PJXCard>
  <PJXCardHeader title="Quarterly report"/>
  <PJXCardBody>Revenue grew 12% over Q1.</PJXCardBody>
  <PJXCardFooter>Updated today</PJXCardFooter>
</PJXCard>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `str` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Pre-rendered children (header + body + footer parts). |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-card-bg` | `var(--surface-alt)` |
    | `--pjx-card-border` | `var(--border)` |
    | `--pjx-card-radius` | `var(--radius-md)` |
    | `--pjx-card-title-color` | `var(--text)` |
    | `--pjx-card-padding` | `var(--space-4, 1rem)` |

??? note "DOM & classes"

    Root `article.pjx-card`; no JS API.

    **Classes:** `pjx-card`.

??? note "Python"

    ```python
    PJXCard(content=PJXCardHeader(title="Quarterly report").render() + PJXCardBody(content="Revenue grew 12% over Q1.").render() + PJXCardFooter(content="Updated today").render())
    ```

### PJXCardHeader

Card header region. When `title` is set it renders `<h3 class="pjx-card__title">` inside the header; when `title` is empty the `content` slot is rendered directly instead. **Assets:** `pjx-card-header.css` only.

```html
<PJXCard>
  <PJXCardHeader title="Quarterly report"/>
  <PJXCardBody>…</PJXCardBody>
  <PJXCardFooter>…</PJXCardFooter>
</PJXCard>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `title` | `str` | `""` | Convenience shorthand — renders `<h3 class="pjx-card__title">` when set; takes precedence over `content`. |
    | `class_name` | `str` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Rich header slot; used when `title` is empty. |

??? note "DOM & classes"

    Root `header.pjx-card__header`; no JS API.

    **Classes:** `pjx-card__header`, `pjx-card__title`.

??? note "Python"

    ```python
    PJXCardHeader(title="Quarterly report")
    ```

### PJXCardBody

Card body region. **Assets:** `pjx-card-body.css` only.

```html
<PJXCard>
  <PJXCardHeader title="Quarterly report"/>
  <PJXCardBody>Revenue grew 12% over Q1.</PJXCardBody>
  <PJXCardFooter>…</PJXCardFooter>
</PJXCard>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `str` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Main card content. |

??? note "DOM & classes"

    Root `div.pjx-card__body`; no JS API.

    **Classes:** `pjx-card__body`.

??? note "Python"

    ```python
    PJXCardBody(content="Revenue grew 12% over Q1.")
    ```

### PJXCardFooter

Card footer region. **Assets:** `pjx-card-footer.css` only.

```html
<PJXCard>
  <PJXCardHeader title="Quarterly report"/>
  <PJXCardBody>…</PJXCardBody>
  <PJXCardFooter>Updated today</PJXCardFooter>
</PJXCard>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `str` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Footer content (actions, metadata, etc.). |

??? note "DOM & classes"

    Root `footer.pjx-card__footer`; no JS API.

    **Classes:** `pjx-card__footer`.

??? note "Python"

    ```python
    PJXCardFooter(content="Updated today")
    ```

### PJXDivider

Separator line. **Assets:** `pjx_divider.css` only.

<!-- demo: PJXDivider -->

```html
<PJXDivider orientation="horizontal" label="or continue with"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `orientation` | literal | `"horizontal"` | `horizontal` (default `hr`) or `vertical` (bar). |
    | `label` | `str` | `""` | If set with horizontal orientation, flex row with label between lines. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-divider-color` | `var(--border)` |
    | `--pjx-divider-thickness` | `1px` |
    | `--pjx-divider-gap` | `0.75rem` |
    | `--pjx-divider-label-color` | `var(--text-muted)` |
    | `--pjx-divider-label-size` | `var(--font-size-sm)` |

??? note "DOM & classes"

    Root `.pjx-divider`; no JS API.

    **Classes:** `pjx-divider--horizontal`, `pjx-divider--vertical`, `pjx-divider--labeled`, `pjx-divider__line`, `pjx-divider__label`.

??? note "Python"

    ```python
    PJXDivider(orientation="horizontal", label="or continue with")
    ```

### PJXSpinner

Inline loading indicator. **Assets:** `pjx_spinner.css` only.

<!-- demo: PJXSpinner -->

```html
<PJXSpinner size="sm" label="Loading data"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `size` | literal | `"md"` | `sm`, `md`, or `lg`. |
    | `label` | `str` | `"Loading"` | Visually hidden; exposed to assistive tech. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-spinner-sm` | `1.25rem` |
    | `--pjx-spinner-md` | `2rem` |
    | `--pjx-spinner-lg` | `2.75rem` |
    | `--pjx-spinner-track` | `color-mix(in srgb, var(--text-muted) 35%, transparent)` |
    | `--pjx-spinner-accent` | `var(--brand)` |

??? note "DOM & classes"

    Root `.pjx-spinner`; no JS API.

    **Classes:** `pjx-spinner`, `pjx-spinner--sm|md|lg`, `pjx-spinner__ring`, `pjx-spinner__label` (screen-reader-only).

??? note "Python"

    ```python
    PJXSpinner(size="sm", label="Loading data")
    ```

### PJXAvatar

Image or initials in a circle. **Assets:** `pjx_avatar.css` only.

<!-- demo: PJXAvatar -->

```html
<PJXAvatar initials="JD" size="sm" alt="Jane Doe"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `src` | `str` | `""` | Image URL; when empty, initials fallback is shown. |
    | `alt` | `str` | `""` | `img` alt text; also used as `title` on initials. |
    | `initials` | `str` | `""` | Up to two characters (trimmed/capped in validation). |
    | `size` | `str \| int` | `"md"` | Named token (`sm`, `md`, `lg`) **or** an arbitrary pixel size (`int`) or CSS length string (`"36px"`, `"2.5rem"`). Named tokens emit the BEM modifier class; an int/CSS length renders `width`/`height` inline. |
    | `color` | `str` | `""` | Inline `background` color (e.g. `"#4f46e5"`, `"hsl(240 60% 50%)"` ). |

    **Arbitrary pixel sizing:** pass an `int` for a pixel size or any CSS length string for a custom size. This bypasses the named-token classes so the avatar can be sized by data rather than the three design-system tokens.

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-avatar-sm` | `2rem` |
    | `--pjx-avatar-md` | `2.5rem` |
    | `--pjx-avatar-lg` | `3.25rem` |
    | `--pjx-avatar-bg` | `var(--surface-alt)` |
    | `--pjx-avatar-fg` | `var(--text-muted)` |
    | `--pjx-avatar-border` | `var(--border)` |

??? note "DOM & classes"

    Root `.pjx-avatar`; no JS API.

    **Classes:** `pjx-avatar`, `pjx-avatar--sm|md|lg` (named tokens only), `pjx-avatar__img`, `pjx-avatar__initials`.

??? note "Python"

    ```python
    PJXAvatar(initials="JD", size="sm", alt="Jane Doe")
    ```

### PJXAvatarStack

Overlapping row of avatars with optional overflow count. **Assets:** `pjx-avatar-stack.css` only.

<!-- demo: PJXAvatarStack -->

```html
<PJXAvatarStack extra_count="4">
  <PJXAvatar initials="AB" size="sm" alt="Alice Brown"/>
  <PJXAvatar initials="CD" size="sm" alt="Carol Davis"/>
  <PJXAvatar initials="EF" size="sm" alt="Eve Foster"/>
</PJXAvatarStack>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `avatars` | `list[dict \| str \| BaseComponent]` | `[]` | Per-avatar items — see below for the two accepted shapes. |
    | `extra_count` | `int` | `0` | When `> 0`, renders a `+N` overflow chip. |
    | `empty_label` | `str` | `""` | When no avatars and `empty_label` is set, renders a fallback label. |

    **Two item shapes are accepted in `avatars`:**

    1. **Structured data dict** — the stack renders its own pill; no child `PJXAvatar` needed.

       | Key | Type | Required | Description |
       | --- | --- | --- | --- |
       | `initials` | `str` | yes | Up to two characters shown in the pill. |
       | `color` | `str` | no | Inline `background` color. |
       | `alt` | `str` | no | `title` tooltip (takes precedence over `name`). |
       | `name` | `str` | no | Fallback tooltip when `alt` is not set. |

    2. **Pre-built item** — an HTML string or any `BaseComponent` instance (original interface, still fully supported).

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-avatar-stack-overlap` | `-0.5rem` |
    | `--pjx-avatar-stack-ring` | `var(--surface)` |

??? note "DOM & classes"

    Root `.pjx-avatar-stack`; no JS API.

    **Classes:** `pjx-avatar-stack`, `pjx-avatar-stack__pill` (dict-rendered pills), `pjx-avatar-stack__more`, `pjx-avatar-stack__empty`.

??? note "Python"

    ```python
    PJXAvatarStack(avatars=[PJXAvatar(initials="AB", size="sm", alt="Alice Brown"), PJXAvatar(initials="CD", size="sm", alt="Carol Davis"), PJXAvatar(initials="EF", size="sm", alt="Eve Foster")], extra_count=4)
    ```

### PJXBreadcrumb

Ordered trail of links. **Assets:** `pjx_breadcrumb.css` only.

<!-- demo: PJXBreadcrumb -->

```html
<PJXBreadcrumb items='[["Home","/"],["Projects","/projects"],["Dashboard",null]]'/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `items` | `list[tuple[str, str \| None]]` | `[]` | `(label, href)` left to right; `href` `None` marks the current page. |
    | `aria_label` | `str` | `"PJXBreadcrumb"` | `aria-label` on the `<nav>` wrapper. |

    `items` may also be passed as a **JSON array** string (e.g. from PascalCase tags): `[["Home","/"],["Here",null]]`.

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-breadcrumb-sep` | `"/"` |
    | `--pjx-breadcrumb-link-color` | `var(--brand)` |
    | `--pjx-breadcrumb-current-color` | `var(--text)` |

??? note "DOM & classes"

    Root `.pjx-breadcrumb`; no JS API.

    **Classes:** `pjx-breadcrumb`, `pjx-breadcrumb__list`, `pjx-breadcrumb__item`, `pjx-breadcrumb__link`, `pjx-breadcrumb__current`. Separators via `::after` on items except the last.

??? note "Python"

    ```python
    PJXBreadcrumb(items=[("Home", "/"), ("Projects", "/projects"), ("Dashboard", None)])
    ```

### PJXSkeleton

Placeholder shimmer blocks. **Assets:** `pjx_skeleton.css` only.

<!-- demo: PJXSkeleton -->

```html
<PJXSkeleton variant="text" lines="3"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `variant` | literal | `"text"` | `text` (stacked lines), `circle`, or `rect`. |
    | `lines` | `int` | `3` | For `text`, count of `pjx-skeleton__line` rows. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-skeleton-bg` | `var(--surface-alt)` |
    | `--pjx-skeleton-shine` | `color-mix(in srgb, var(--text) 8%, var(--surface-alt))` |
    | `--pjx-skeleton-line-height` | `0.65rem` |
    | `--pjx-skeleton-line-gap` | `0.5rem` |
    | `--pjx-skeleton-circle-size` | `2.5rem` |
    | `--pjx-skeleton-rect-height` | `6rem` |
    | `--pjx-skeleton-rect-radius` | `var(--radius-md)` |
    | `--pjx-skeleton-duration` | `1.2s` |

??? note "DOM & classes"

    Root `.pjx-skeleton`; no JS API.

    **Classes:** `pjx-skeleton`; variant modifiers `pjx-skeleton--text`, `--circle`, `--rect`; `pjx-skeleton__line`, `pjx-skeleton__circle`, `pjx-skeleton__rect`.

??? note "Python"

    ```python
    PJXSkeleton(variant="text", lines=3)
    ```

### PJXProgress

Determinate or indeterminate meter. **Assets:** `pjx_progress.css` only.

<!-- demo: PJXProgress -->

```html
<PJXProgress value="65" max="100" label="Upload progress"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `value` | `float \| None` | `None` | Omit or `None` for indeterminate `<progress>`. |
    | `max` | `float` | `100` | Passed to `<progress max="…">`. |
    | `label` | `str` | `""` | Optional `pjx-progress__label`; wires `aria-labelledby` when set. |
    | `loading_label` | `str` | `"Loading"` | `aria-label` fallback on `<progress>` when `label` is empty. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-progress-height` | `0.5rem` |
    | `--pjx-progress-radius` | `var(--radius-full)` |
    | `--pjx-progress-track` | `var(--surface-alt)` |
    | `--pjx-progress-fill` | `var(--brand)` |
    | `--pjx-progress-indeterminate-speed` | `1.2s` |

??? note "DOM & classes"

    Root `.pjx-progress`; no JS API.

    **Classes:** `pjx-progress`, `pjx-progress__label`, `pjx-progress__bar`.

??? note "Python"

    ```python
    PJXProgress(value=65, max=100, label="Upload progress")
    ```

### PJXEmptyState

Centered, vertically-stacked empty-view container. Compose whatever you like inside via `content`. **Assets:** `pjx-empty-state.css` only (template file **`pjx-empty-state.html`** next to `pjx_empty_state.py`).

<!-- demo: PJXEmptyState -->

```html
<PJXEmptyState>
  <h3>No results</h3>
  <p>Try a different search term.</p>
</PJXEmptyState>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `content` | `str \| BaseComponent` | `""` | Freeform inner content (rendered as-is). |
    | `suggestions` | `list[dict]` | `[]` | Interactive suggestion chips; each dict dispatches a custom event on click. See below. |
    | `class_name` | `str` | `""` | Extra CSS class(es) appended to the root element. |

    **Suggestion chips** (`suggestions`) provide a first-class "click a chip → dispatch an event" pattern — the common use case of filling an input or triggering a quick action without navigation.

    Each item in `suggestions` is a dict with:

    | Key | Type | Required | Description |
    | --- | --- | --- | --- |
    | `label` | `str` | yes | Visible chip text. |
    | `value` | `str` | no | Value dispatched in the event payload; defaults to `label`. |
    | `event` | `str` | no | Custom event name; defaults to `"pjx:suggestion"`. |

    The rendered chip uses Alpine's `$dispatch`, so any parent can listen with `@pjx:suggestion.window="..."` (or the custom event name). The dispatched detail is `{ value: "<chip value>" }`.

    ```html
    <!-- Listener in a parent template -->
    <textarea @pjx:suggestion.window="$el.value = $event.detail.value"></textarea>
    ```

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-empty-state-padding` | `2rem 1.5rem` |
    | `--pjx-empty-state-max-width` | `28rem` |
    | `--pjx-empty-state-gap` | `0.5rem` |
    | `--pjx-empty-state-actions-gap` | `0.5rem` (chip row gap) |
    | `--pjx-empty-state-chip-bg` | `var(--surface-alt)` |
    | `--pjx-empty-state-chip-color` | `var(--text-muted)` |
    | `--pjx-empty-state-chip-border` | `var(--border)` |

??? note "DOM & classes"

    Root `.pjx-empty-state`; no JS API (suggestion chips require Alpine for `$dispatch`).

    **Classes:** `pjx-empty-state`, `pjx-empty-state__suggestions`, `pjx-empty-state__chip`.

??? note "Python"

    ```python
    PJXEmptyState(content="<h3>No results</h3><p>Try a different search term.</p>", suggestions=[{"label": "Draft a message"}, {"label": "Summarise a thread"}])
    ```

### PJXIcon

Inline SVG icon from a vendored [Lucide](https://lucide.dev) set (ISC). **Assets:** `pjx-icon.css` only.

<!-- demo: PJXIcon -->

```html
<PJXIcon name="plus" size="24" label="Add"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `name` | `str` | *(required)* | Icon key into the vendored set (e.g. `chevron-right`, `plus`, `search`). An unknown name renders a hidden placeholder (nothing visible) and logs a warning. |
    | `size` | `int \| str` | `16` | `int` → `width`/`height` in px; `str` → used verbatim as a CSS length. |
    | `stroke_width` | `float` | `1.5` | SVG `stroke-width`. |
    | `label` | `str \| None` | `None` | `None` → `aria-hidden="true"`; a string → `role="img"` + a `<title>`. |

??? note "DOM & classes"

    Root `<svg>` with `stroke="currentColor"` and `fill="none"`; no JS API. It inherits text color, so it themes for free — set `color` on the icon or any ancestor. Compose into `content`, e.g. `<PJXButton variant="primary"><PJXIcon name="plus"/> Add</PJXButton>`.

    **Classes:** `pjx-icon`. No `--pjx-icon-*` tokens — size comes from the `size`/`stroke_width` props and color from `currentColor`.

??? note "Python"

    ```python
    PJXIcon(name="plus", size=24, label="Add")
    ```

### PJXButton

Structural, themeable button. Composes [`PJXRegionLoader`](#pjxregionloader) for the inline loading state. **Assets:** `pjx-button.css` only.

<!-- demo: PJXButton -->

```html
<PJXButton content="Save" variant="primary"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `content` | `str \| BaseComponent` | `""` | Freeform button content (rendered raw); nest icons, text, or any markup here. The loading spinner auto-appends after this. |
    | `variant` | `str` | `"default"` | Class hook only → `pjx-button--{variant}`. No baked palette; style it yourself. |
    | `block` | `bool` | `False` | Full-width (`pjx-button--block`) instead of content-width. |
    | `loading` | `bool` | `False` | Renders a `<PJXRegionLoader/>` overlay and sets `aria-busy="true"`. |
    | `disabled` | `bool` | `False` | Sets the `disabled` attribute. |
    | `type` | literal | `"button"` | `button`, `submit`, or `reset`. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-button-bg` | `transparent` |
    | `--pjx-button-color` | `inherit` |
    | `--pjx-button-border` | `1px solid currentColor` |
    | `--pjx-button-radius` | `0.375rem` |
    | `--pjx-button-padding` | `0.5rem 0.875rem` |
    | `--pjx-button-gap` | `0.5rem` |
    | `--pjx-button-font-size` | `inherit` |
    | `--pjx-button-font-weight` | `500` |
    | `--pjx-button-bg-hover` | `var(--pjx-button-bg)` |
    | `--pjx-button-border-hover` | `currentColor` |

??? note "DOM & classes"

    Root `<button>` rendering `{{ content }}` verbatim. No JS API — pass `hx-*`/`@click` inline (they pass through to the root). The default `.pjx-button` is visually neutral so it never fights your design system; paint variants via `.pjx-button--<variant>`.

    **Classes:** `pjx-button`; `pjx-button--block`; variant seams `pjx-button--<variant>`.

??? note "Python"

    ```python
    PJXButton(content="Save", variant="primary")
    ```

### PJXAccordion

Collapsible section built on native `<details>`. Composed with `PJXAccordionTrigger` (the `<summary>`, with the auto chevron) and `PJXAccordionContent` (the body). **Assets:** `pjx-accordion.css` (shell radius only — trigger and chevron CSS ship with `PJXAccordionTrigger`). No JS.

<!-- demo: PJXAccordion -->

```html
<PJXAccordion>
  <PJXAccordionTrigger>What is pyjinhx?</PJXAccordionTrigger>
  <PJXAccordionContent><p>A Python/Jinja HTML component framework.</p></PJXAccordionContent>
</PJXAccordion>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `open` | `bool` | `True` | Initial expanded state (renders the `open` attribute on `<details>`). |
    | `group` | `str \| None` | `None` | Native `<details name="...">` for exclusive-open groups; default is independent multi-open. |
    | `content` | `str \| BaseComponent` | `""` | Inner HTML; nest a `PJXAccordionTrigger` + `PJXAccordionContent` here. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-accordion-radius` | `0` |
    | `--pjx-accordion-trigger-bg` | `transparent` |
    | `--pjx-accordion-trigger-color` | `inherit` |
    | `--pjx-accordion-trigger-padding` | `0.5rem 0.75rem` |
    | `--pjx-accordion-trigger-font-size` | `inherit` |
    | `--pjx-accordion-trigger-font-weight` | `500` |
    | `--pjx-accordion-trigger-bg-hover` | `var(--pjx-accordion-trigger-bg)` |
    | `--pjx-accordion-chevron-size` | `1em` |

??? note "DOM & classes"

    Root `<details class="pjx-accordion">` rendering `{{ content }}` verbatim. Place a `PJXAccordionTrigger` and a `PJXAccordionContent` inside `content` to form a complete accordion.

    **Classes:** `pjx-accordion`.

??? note "Python"

    ```python
    PJXAccordion(content=PJXAccordionTrigger(content="What is pyjinhx?").render() + PJXAccordionContent(content="<p>A Python/Jinja HTML component framework.</p>").render())
    ```

### PJXAccordionTrigger

The `<summary>` part of a composed accordion. Composes [`PJXIcon`](#pjxicon) for the disclosure chevron. **Assets:** `pjx-accordion-trigger.css` (trigger + chevron styles), `pjx-accordion-trigger.js` (toggle-suppression for opt-in `pjx-accordion__actions`).

```html
<PJXAccordion>
  <PJXAccordionTrigger>What is pyjinhx?</PJXAccordionTrigger>
  <PJXAccordionContent>…</PJXAccordionContent>
</PJXAccordion>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `disabled` | `bool` | `False` | Marks the summary `aria-disabled="true"` + `tabindex="-1"` (and `pointer-events: none` via CSS). |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) for the root element. |
    | `content` | `str \| BaseComponent` | `""` | Trigger label (text or rich markup). |

    **Actions (opt-in).** To add non-toggling action buttons, wrap them in `<div class="pjx-accordion__actions">` inside `content`. `pjx-accordion-trigger.js` registers a single capture-phase `click` listener that calls `preventDefault()` (only — deliberately **not** `stopPropagation()`) for any click inside `.pjx-accordion__actions`. This cancels the native `<summary>` toggle while leaving htmx and other handlers intact.

??? note "DOM & classes"

    Root `<summary class="pjx-accordion__trigger">` containing the auto-chevron and `content`. The chevron rotates on `[open]` via CSS. The default marker is stripped.

    **Classes:** `pjx-accordion__trigger`, `pjx-accordion__chevron`, `pjx-accordion__actions`.

??? note "Python"

    ```python
    PJXAccordionTrigger(content="What is pyjinhx?")
    ```

### PJXAccordionContent

The body part of a composed accordion. **Assets:** none (unstyled wrapper; use your own or theme the parent shell).

```html
<PJXAccordion>
  <PJXAccordionTrigger>What is pyjinhx?</PJXAccordionTrigger>
  <PJXAccordionContent><p>A Python/Jinja HTML component framework.</p></PJXAccordionContent>
</PJXAccordion>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) for the root element. |
    | `content` | `str \| BaseComponent` | `""` | Body content. |

??? note "DOM & classes"

    Root `<div class="pjx-accordion__content">` rendering `{{ content }}` verbatim.

    **Classes:** `pjx-accordion__content`. No theming tokens — style via the parent `pjx-accordion` or your own rules.

??? note "Python"

    ```python
    PJXAccordionContent(content="<p>A Python/Jinja HTML component framework.</p>")
    ```

### PJXAccordionGroup

Groups a set of `PJXAccordion`s into a shared layout/behavior container. Handles exclusive-open coordination in JS so you don't need to stamp a `group=` on every child. **Assets:** `pjx-accordion-group.css`, `pjx-accordion-group.js`.

<!-- demo: PJXAccordionGroup -->

```html
<PJXAccordionGroup mode="exclusive" gap="0.25rem">
  <PJXAccordion>
    <PJXAccordionTrigger>Section A</PJXAccordionTrigger>
    <PJXAccordionContent><p>Content A.</p></PJXAccordionContent>
  </PJXAccordion>
  <PJXAccordion open="False">
    <PJXAccordionTrigger>Section B</PJXAccordionTrigger>
    <PJXAccordionContent><p>Content B.</p></PJXAccordionContent>
  </PJXAccordion>
</PJXAccordionGroup>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `mode` | `"exclusive" \| "multi"` | `"multi"` | `exclusive` — at most one child `<details>` open at a time (JS-coordinated via `toggle` capture); `multi` — independent. |
    | `gap` | `str` | `"0"` | Space between accordion items; written to `--pjx-accordion-group-gap` inline on the root. |
    | `default_open` | `"none" \| "first" \| "all"` | `"none"` | Which items start open on mount. `none` — no change (each child respects its own `open` prop); `first` — JS opens the first direct `<details>` child; `all` — JS opens all direct `<details>` children. Applied by `pjx-accordion-group.js` after DOM settle. |
    | `content` | `str \| BaseComponent` | `""` | Children (nested `PJXAccordion`s or raw HTML). |

    **`default_open` is JS-driven.** The group receives its `content` as a pre-rendered string, so it cannot set the `open` attribute on individual child elements at the server level. Instead, `data-default-open` is emitted on the root div and `pjx-accordion-group.js` opens the appropriate children on mount (and after every htmx swap). Per-child `open=True/False` props are still respected when `default_open="none"`.

    **JS is always loaded with the group asset.** The script is a compact guarded IIFE; it exits early per-element when neither `mode="exclusive"` nor `data-default-open` requires action. In pure `multi` mode with `default_open="none"` (the defaults) the only runtime cost is the per-element `data-pjx-group-init` guard check.

    **Design decision — JS vs native `<details name>`.** Native `<details name="...">` provides exclusive-open without JS, but requires stamping the same `name` on every child element. `PJXAccordion.group=` exposes this as an explicit per-child opt-in (still supported, not deprecated). `PJXAccordionGroup(mode="exclusive")` is the composition-friendly alternative: the group's capture-phase `toggle` listener handles exclusive-open so callers don't set `group=` on every child. The two approaches are independent and can coexist.

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-accordion-group-gap` | `0` |

??? note "DOM & classes"

    Root `<div class="pjx-accordion-group" data-pjx-accordion-group data-mode="..." [data-default-open="..."]>`. `pjx-accordion-group.js` runs once per element (guarded by `data-pjx-group-init`), applies `default_open`, then wires the exclusive-open `toggle` listener when `mode="exclusive"`. Re-initialized on `htmx:afterSettle`.

    **Classes:** `pjx-accordion-group`.

??? note "Python"

    ```python
    PJXAccordionGroup(mode="exclusive", gap="0.25rem", content=PJXAccordion(content=PJXAccordionTrigger(content="Section A").render() + PJXAccordionContent(content="<p>Content A.</p>").render()).render() + PJXAccordion(open=False, content=PJXAccordionTrigger(content="Section B").render() + PJXAccordionContent(content="<p>Content B.</p>").render()).render())
    ```

### PJXTable

Accessible data table shell. Compose with `PJXTableHead`, `PJXTableBody`, `PJXTableRow`, `PJXTableHeaderCell`, and `PJXTableCell` parts. **Assets:** `pjx-table.css`.

<!-- demo: PJXTable -->

```html
<PJXTable caption="Team members" striped="true" bordered="horizontal">
  <PJXTableHead>
    <PJXTableRow>
      <PJXTableHeaderCell sortable="true" sort="asc">Name</PJXTableHeaderCell>
      <PJXTableHeaderCell>Role</PJXTableHeaderCell>
    </PJXTableRow>
  </PJXTableHead>
  <PJXTableBody>
    <PJXTableRow selectable="true" value="1"><PJXTableCell>Ada Lovelace</PJXTableCell><PJXTableCell>Engineer</PJXTableCell></PJXTableRow>
    <PJXTableRow selectable="true" value="2"><PJXTableCell>Alan Turing</PJXTableCell><PJXTableCell>Researcher</PJXTableCell></PJXTableRow>
  </PJXTableBody>
</PJXTable>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `caption` | `str` | `""` | `<caption>` text; suppressed when empty. |
    | `striped` | `bool` | `False` | Alternating row shading via `pjx-table--striped`. |
    | `sticky_header` | `bool` | `False` | Keeps the `<thead>` visible on scroll via `pjx-table--sticky`. |
    | `density` | `"comfortable" \| "compact"` | `"comfortable"` | Cell padding scale → `pjx-table--density-compact` when `"compact"`; no class for `"comfortable"` or `"none"`. |
    | `bordered` | `"none" \| "horizontal" \| "all"` | `"none"` | Border style → `pjx-table--bordered-{bordered}` (omitted when `"none"`). |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Pre-rendered children (`PJXTableHead` + `PJXTableBody`). |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-table-border` | `var(--border)` |
    | `--pjx-table-header-bg` | `var(--surface-alt)` |
    | `--pjx-table-header-fg` | `var(--text)` |
    | `--pjx-table-stripe-bg` | `var(--surface-alt)` |
    | `--pjx-table-row-hover-bg` | `var(--surface-alt)` |
    | `--pjx-table-cell-pad-y` | `0.5rem` |
    | `--pjx-table-cell-pad-x` | `0.75rem` |

??? note "DOM & classes"

    Root `<table class="pjx-table">` with an optional `<caption class="pjx-table__caption">` as its first child. No JS public API — sort state is reflected via `aria-sort` on `<th>` cells and driven by your own htmx/Alpine handlers on `PJXTableHeaderCell`.

    **Classes:** `pjx-table`, `pjx-table--striped`, `pjx-table--sticky`, `pjx-table--density-compact`, `pjx-table--bordered-horizontal`, `pjx-table--bordered-all`.

??? note "Python"

    ```python
    PJXTable(
        caption="Team members",
        striped=True,
        bordered="horizontal",
        content=(
            PJXTableHead(content=PJXTableRow(content=(
                PJXTableHeaderCell(sortable=True, sort="asc", content="Name").render()
                + PJXTableHeaderCell(content="Role").render()
            )).render()).render()
            + PJXTableBody(content=(
                PJXTableRow(selectable=True, value="1", content=(
                    PJXTableCell(content="Ada Lovelace").render()
                    + PJXTableCell(content="Engineer").render()
                )).render()
                + PJXTableRow(selectable=True, value="2", content=(
                    PJXTableCell(content="Alan Turing").render()
                    + PJXTableCell(content="Researcher").render()
                )).render()
            )).render()
        ),
    )
    ```

### PJXTableHead

`<thead>` wrapper for a composed table. **Assets:** none (styled via `pjx-table.css`).

```html
<PJXTable>
  <PJXTableHead>
    <PJXTableRow>
      <PJXTableHeaderCell>Name</PJXTableHeaderCell>
    </PJXTableRow>
  </PJXTableHead>
</PJXTable>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Pre-rendered `PJXTableRow` children. |

??? note "DOM & classes"

    Root `<thead class="pjx-table__head">` rendering `{{ content }}` verbatim.

    **Classes:** `pjx-table__head`.

??? note "Python"

    ```python
    PJXTableHead(content=PJXTableRow(content=PJXTableHeaderCell(content="Name").render()).render())
    ```

### PJXTableBody

`<tbody>` wrapper for a composed table. **Assets:** none (styled via `pjx-table.css`).

```html
<PJXTable>
  <PJXTableBody>
    <PJXTableRow><PJXTableCell>Ada Lovelace</PJXTableCell></PJXTableRow>
  </PJXTableBody>
</PJXTable>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Pre-rendered `PJXTableRow` children. |

??? note "DOM & classes"

    Root `<tbody class="pjx-table__body">` rendering `{{ content }}` verbatim.

    **Classes:** `pjx-table__body`.

??? note "Python"

    ```python
    PJXTableBody(content=PJXTableRow(content=PJXTableCell(content="Ada Lovelace").render()).render())
    ```

### PJXTableRow

A `<tr>` for either the head or body section. When `selectable=True`, a checkbox cell is auto-prepended on the body row. **Assets:** none (styled via `pjx-table.css`).

```html
<PJXTableRow selectable="true" value="1">
  <PJXTableCell>Ada Lovelace</PJXTableCell>
  <PJXTableCell>Engineer</PJXTableCell>
</PJXTableRow>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `selectable` | `bool` | `False` | Auto-prepends a checkbox `<td>` with `name="selected"` and `value="{{ value }}"`. |
    | `value` | `str` | `""` | Checkbox value emitted when the row is selected. |
    | `select_label` | `str` | `"Select row"` | `aria-label` on the auto-prepended checkbox. |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Pre-rendered cell children. |

    **Select-all alignment.** When using `selectable` rows, add a leading `PJXTableHeaderCell` to the head row (empty, or a select-all checkbox you wire with htmx/Alpine) so the columns align — `selectable` only auto-prepends a checkbox on body rows.

??? note "DOM & classes"

    Root `<tr class="pjx-table__row">`; `pjx-table__row--selectable` added when `selectable=True`.

    **Classes:** `pjx-table__row`, `pjx-table__row--selectable`.

??? note "Python"

    ```python
    PJXTableRow(selectable=True, value="1", content=PJXTableCell(content="Ada Lovelace").render() + PJXTableCell(content="Engineer").render())
    ```

### PJXTableHeaderCell

A `<th>` for use inside `PJXTableRow` in the head section. Reflects sort direction via `aria-sort`. **Assets:** none (styled via `pjx-table.css`).

```html
<PJXTableHeaderCell sortable="true" sort="asc">Name</PJXTableHeaderCell>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `sortable` | `bool` | `False` | Adds `pjx-table__th--sortable` and a sort-direction indicator. |
    | `sort` | `"none" \| "asc" \| "desc"` | `"none"` | Current sort direction → `aria-sort` attribute; `"none"` omits `aria-sort`. |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Column header label. |

??? note "DOM & classes"

    Root `<th class="pjx-table__th" scope="col">`. When `sortable=True`: `pjx-table__th--sortable` is added and `aria-sort` is set when `sort` is `"asc"` or `"desc"`.

    **Classes:** `pjx-table__th`, `pjx-table__th--sortable`.

??? note "Python"

    ```python
    PJXTableHeaderCell(sortable=True, sort="asc", content="Name")
    ```

### PJXTableCell

A `<td>` for use inside `PJXTableRow` in the body section. **Assets:** none (styled via `pjx-table.css`).

```html
<PJXTableCell>Ada Lovelace</PJXTableCell>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Cell content. |

??? note "DOM & classes"

    Root `<td class="pjx-table__cell">` rendering `{{ content }}` verbatim.

    **Classes:** `pjx-table__cell`.

??? note "Python"

    ```python
    PJXTableCell(content="Ada Lovelace")
    ```

## Overlays & dialogs

### PJXModal

Native `<dialog>` shell. Compose with `PJXModalHeader`, `PJXModalBody`, and `PJXModalFooter` for structured layouts. **Assets:** `pjx-modal.css`, `pjx-modal.js`.

<!-- demo: PJXModal -->

```html
<PJXModal id="demo-modal">
  <PJXModalHeader id="demo-modal-h" title="Confirm changes"/>
  <PJXModalBody id="demo-modal-b">Your draft will be published immediately. This action cannot be undone.</PJXModalBody>
  <PJXModalFooter id="demo-modal-f"><button class="pjx-demo-btn" data-pjx-close>Cancel</button></PJXModalFooter>
</PJXModal>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `content` | `str \| BaseComponent` | `""` | Inner content (part components or arbitrary markup). |
    | `open_on_mount` | `bool` | `False` | When `True`, adds `data-pjx-open-on-mount`; JS opens the dialog as soon as it mounts (e.g. via `hx-swap="beforeend"`). |
    | `remove_on_close` | `bool` | `False` | When `True`, adds `data-pjx-remove-on-close`; JS removes the element from the DOM on close. |
    | `class_name` | `str` | `""` | Extra CSS classes on the root `<dialog>`. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-modal-width` | `52rem` |
    | `--pjx-modal-min-height` | `28rem` |
    | `--pjx-modal-bg` | `var(--surface)` |
    | `--pjx-modal-border` | `var(--border)` |
    | `--pjx-modal-radius` | `var(--radius-lg)` |
    | `--pjx-modal-shadow` | `var(--shadow-md)` |
    | `--pjx-modal-header-bg` | `var(--surface-alt)` |
    | `--pjx-modal-header-sep` | `var(--border)` |
    | `--pjx-modal-footer-bg` | `var(--surface-alt)` |
    | `--pjx-modal-footer-sep` | `var(--border)` |
    | `--pjx-modal-title-color` | `var(--text)` |
    | `--pjx-modal-close-color` | `var(--text-muted)` |
    | `--pjx-modal-backdrop` | `rgb(0 0 0 / 0.6)` |
    | `--pjx-modal-padding` | `1.5rem` |

    Close control hover uses `var(--surface)`, `var(--text)`, `var(--radius-sm)`, `var(--transition)` from your theme.

??? note "DOM & classes"

    Root `dialog.pjx-modal` (state: `[open]`, `.pjx-modal--closing`).
    Attributes: `data-pjx-open="<id>"` on any element opens it on click; `data-pjx-close` inside closes it;
    `data-pjx-open-on-mount`, `data-pjx-remove-on-close` reflect the lifecycle props.
    Events (bubble from the root): `pjx:modal:before-open`*, `pjx:modal:open`,
    `pjx:modal:before-close`*, `pjx:modal:close` — `*` = cancelable, `detail = {reason, trigger}`,
    `reason ∈ escape|backdrop|api|trigger`. API: `pjx.modal.open(id)`, `pjx.modal.close(id)`.

    **Classes:** `pjx-modal`; closing state `pjx-modal--closing`; `pjx-modal__box`. Part-component classes (`__header`, `__title`, `__close`, `__body`, `__footer`) belong to the respective part components below.

??? note "Python"

    ```python
    PJXModal(
        id="demo-modal",
        content=(
            PJXModalHeader(id="demo-modal-h", title="Confirm changes").render()
            + PJXModalBody(id="demo-modal-b", content="Your draft will be published immediately. This action cannot be undone.").render()
            + PJXModalFooter(id="demo-modal-f", content='<button class="pjx-demo-btn" data-pjx-close>Cancel</button>').render()
        ),
    )
    ```

### PJXModalHeader

Header part for `PJXModal`. Renders a `<header>` inside the modal box; always includes a close button. **Assets:** `pjx-modal-header.css`.

```html
<PJXModalHeader title="Delete file?"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `title` | `str` | `""` | When set, renders `<span class="pjx-modal__title">` with this text (escaped); when empty, `{{ content }}` is used instead. |
    | `close_label` | `str` | `"Close"` | `aria-label` for the auto-included close button. |
    | `close_content` | `str` | `"✕"` | Inner markup/text of the close button. |
    | `class_name` | `str` | `""` | Extra CSS classes on the `<header>`. |
    | `content` | `str \| BaseComponent` | `""` | Custom header body; used when `title` is empty. |

??? note "DOM & classes"

    **Classes:** `pjx-modal__header`, `pjx-modal__title`, `pjx-modal__close`.

??? note "Python"

    ```python
    PJXModalHeader(title="Delete file?")
    ```

### PJXModalBody

Body part for `PJXModal`. Renders a `<div class="pjx-modal__body">`. **Assets:** `pjx-modal-body.css`.

```html
<PJXModalBody>This cannot be undone.</PJXModalBody>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `str` | `""` | Extra CSS classes on the body `<div>`. |
    | `content` | `str \| BaseComponent` | `""` | Main content. |

??? note "DOM & classes"

    **Classes:** `pjx-modal__body`.

??? note "Python"

    ```python
    PJXModalBody(content="This cannot be undone.")
    ```

### PJXModalFooter

Footer part for `PJXModal`. Renders a `<footer class="pjx-modal__footer">`. **Assets:** `pjx-modal-footer.css`.

```html
<PJXModalFooter><PJXButton content="Delete"/></PJXModalFooter>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `str` | `""` | Extra CSS classes on the `<footer>`. |
    | `content` | `str \| BaseComponent` | `""` | Footer content (e.g. action buttons). |

??? note "DOM & classes"

    **Classes:** `pjx-modal__footer`.

??? note "Python"

    ```python
    PJXModalFooter(content=PJXButton(content="Delete").render())
    ```

### PJXDrawer

`<dialog>` shell sheet from an edge. **Assets:** `pjx-drawer.css`, `pjx-drawer.js` (JS stays on the shell; each part ships its own CSS — see [PJXDrawerHeader](#pjxdrawerheader), [PJXDrawerBody](#pjxdrawerbody), [PJXDrawerFooter](#pjxdrawerfooter)).

<!-- demo: PJXDrawer -->

```html
<PJXDrawer id="demo-drawer" side="right">
  <PJXDrawerHeader id="demo-drawer-h" title="Filter results"/>
  <PJXDrawerBody id="demo-drawer-b"><p>Adjust filters to narrow down your results.</p></PJXDrawerBody>
  <PJXDrawerFooter id="demo-drawer-f"><button class="pjx-demo-btn" data-pjx-close>Done</button></PJXDrawerFooter>
</PJXDrawer>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `side` | literal | `"right"` | `left`, `right`, or `bottom` → `pjx-drawer--{side}`. |
    | `open_on_mount` | `bool` | `False` | Adds `data-pjx-open-on-mount`; JS opens on arrival. |
    | `remove_on_close` | `bool` | `False` | Adds `data-pjx-remove-on-close`; JS removes element on close. |
    | `class_name` | `str` | `""` | Extra CSS classes on the root `<dialog>`. |
    | `content` | `str \| BaseComponent` | `""` | Inner slot; place composable part components here. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-drawer-width` | `min(24rem, 100vw)` |
    | `--pjx-drawer-height-bottom` | `min(50dvh, 28rem)` |
    | `--pjx-drawer-bg` | `var(--surface)` |
    | `--pjx-drawer-border` | `var(--border)` |
    | `--pjx-drawer-shadow` | `var(--shadow-md)` |
    | `--pjx-drawer-backdrop` | `rgb(0 0 0 / 0.45)` |
    | `--pjx-drawer-header-bg` | `var(--surface-alt)` |
    | `--pjx-drawer-header-sep` | `var(--border)` |
    | `--pjx-drawer-footer-bg` | `var(--surface-alt)` |
    | `--pjx-drawer-footer-sep` | `var(--border)` |
    | `--pjx-drawer-padding` | `1rem` |
    | `--pjx-drawer-z` | `250` |

??? note "DOM & classes"

    Root `dialog.pjx-drawer.pjx-drawer--{side}` (state: `[open]`, `.pjx-drawer--closing`).
    `data-pjx-open="<id>"` on any element opens it; `data-pjx-close` inside closes it;
    `data-pjx-open-on-mount`, `data-pjx-remove-on-close` reflect lifecycle props.
    Events: `pjx:drawer:before-open`*, `pjx:drawer:open`, `pjx:drawer:before-close`*, `pjx:drawer:close` — `*` = cancelable, `detail = {reason, trigger}`, `reason ∈ escape|backdrop|api|trigger`.
    API: `pjx.drawer.open(id)`, `pjx.drawer.close(id)`.

    **Classes:** `pjx-drawer`; side modifiers `pjx-drawer--left`, `--right`, `--bottom`; closing state `pjx-drawer--closing`. The inner layout classes (`__header`, `__title`, `__close`, `__body`, `__footer`) belong to the part components — see below.

??? note "Python"

    ```python
    PJXDrawer(
        id="demo-drawer",
        side="right",
        content=(
            PJXDrawerHeader(id="demo-drawer-h", title="Filter results").render()
            + PJXDrawerBody(
                id="demo-drawer-b",
                content="<p>Adjust filters to narrow down your results.</p>",
            ).render()
            + PJXDrawerFooter(
                id="demo-drawer-f",
                content='<button class="pjx-demo-btn" data-pjx-close>Done</button>',
            ).render()
        ),
    )
    ```

### PJXDrawerHeader

Header bar for a `PJXDrawer`. Automatically includes a close button. **Assets:** `pjx-drawer-header.css`.

```html
<PJXDrawerHeader title="Menu"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `title` | `str` | `""` | Renders `<span class="pjx-drawer__title">` when set; omit to use `content` for a fully custom header. |
    | `close_label` | `str` | `"Close"` | `aria-label` for the auto-included close button. |
    | `close_content` | `str` | `"✕"` | Inner HTML/text of the close button. |
    | `class_name` | `str` | `""` | Extra CSS classes on the root `<header>`. |
    | `content` | `str \| BaseComponent` | `""` | Custom header slot used when `title` is not set. |

??? note "DOM & classes"

    Root `<header class="pjx-drawer__header">`. When `title` is set renders `<span class="pjx-drawer__title">`. Always renders a `<button class="pjx-drawer__close" data-pjx-close aria-label="...">`.

    **Classes:** `pjx-drawer__header`, `pjx-drawer__title`, `pjx-drawer__close`.

??? note "Python"

    ```python
    PJXDrawerHeader(title="Menu")
    ```

### PJXDrawerBody

Scrollable body region for a `PJXDrawer`. **Assets:** `pjx-drawer-body.css`.

```html
<PJXDrawerBody>…links…</PJXDrawerBody>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `str` | `""` | Extra CSS classes on the root `<div>`. |
    | `content` | `str \| BaseComponent` | `""` | Body slot. |

??? note "DOM & classes"

    Root `<div class="pjx-drawer__body">`.

    **Classes:** `pjx-drawer__body`.

??? note "Python"

    ```python
    PJXDrawerBody(content="…links…")
    ```

### PJXDrawerFooter

Footer strip for a `PJXDrawer`. **Assets:** `pjx-drawer-footer.css`.

```html
<PJXDrawerFooter>v1.0</PJXDrawerFooter>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `str` | `""` | Extra CSS classes on the root `<footer>`. |
    | `content` | `str \| BaseComponent` | `""` | Footer slot. |

??? note "DOM & classes"

    Root `<footer class="pjx-drawer__footer">`.

    **Classes:** `pjx-drawer__footer`.

??? note "Python"

    ```python
    PJXDrawerFooter(content="v1.0")
    ```

### PJXConfirmDialog

Accessible `<dialog>` singleton that replaces `window.confirm`. Mount once in the layout; `pjx.confirm()` is available everywhere. **Assets:** `pjx-confirm-dialog.css`, `pjx-confirm-dialog.js`.

<!-- demo: PJXConfirmDialog -->

```html
<PJXConfirmDialog id="demo-confirm"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `confirm_label` | `str` | `"Confirm"` | Default OK button text. |
    | `cancel_label` | `str` | `"Cancel"` | Default cancel button text. |

    Intercepts every `hx-confirm="…"` automatically (via `htmx:confirm` event):

    ```html
    <button hx-post="/delete/1"
            hx-confirm="Delete this item?"
            data-pjx-confirm-danger>Delete</button>
    ```

    For non-htmx forms use `data-confirm="…"` on the `<form>`.

    Override labels per-call:

    ```javascript
    const ok = await pjx.confirm("Are you sure?", {
        okLabel: "Yes, delete",
        cancelLabel: "No",
        danger: true,
    });
    if (ok) { /* proceed */ }
    ```

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-confirm-dialog-bg` | `var(--surface)` |
    | `--pjx-confirm-dialog-border` | `var(--border)` |
    | `--pjx-confirm-dialog-radius` | `var(--radius-md)` |
    | `--pjx-confirm-dialog-shadow` | `var(--shadow-md)` |
    | `--pjx-confirm-dialog-backdrop` | `rgb(0 0 0 / 0.5)` |
    | `--pjx-confirm-dialog-danger` | `#b3261e` |

??? note "DOM & classes"

    Root `dialog.pjx-confirm-dialog[data-pjx-dialog="confirm"]` — singleton, matched by `document.querySelector`. `data-pjx-confirm-danger` on the htmx element → OK button gets `.pjx-confirm-dialog__ok--danger`. `data-pjx-confirm-ok` / `data-pjx-confirm-cancel` per-trigger label overrides.
    API: `pjx.confirm(message, {okLabel?, cancelLabel?, danger?}) → Promise<boolean>`.
    Falls back to `window.confirm` if no `PJXConfirmDialog` is mounted.

    **Classes:** `pjx-confirm-dialog`, `pjx-confirm-dialog__card`, `pjx-confirm-dialog__message`, `pjx-confirm-dialog__actions`, `pjx-confirm-dialog__ok`, `pjx-confirm-dialog__ok--danger`, `pjx-confirm-dialog__cancel`.

??? note "Python"

    ```python
    PJXConfirmDialog(id="demo-confirm")
    ```

### PJXPromptDialog

Accessible `<dialog>` singleton that replaces `window.prompt`. Mount once in the layout; `pjx.prompt()` is available everywhere. **Assets:** `pjx-prompt-dialog.css`, `pjx-prompt-dialog.js`.

<!-- demo: PJXPromptDialog -->

```html
<PJXPromptDialog id="demo-prompt"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `input_label` | `str` | `""` | Default label text above the input. |
    | `submit_label` | `str` | `"OK"` | Submit button text. |
    | `cancel_label` | `str` | `"Cancel"` | Cancel button text. |

    ```javascript
    const name = await pjx.prompt("Enter your name", {
        initial: "Alice",
        placeholder: "Full name",
        okLabel: "Save",
    });
    if (name !== null) { /* user submitted */ }
    ```

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-prompt-dialog-bg` | `var(--surface)` |
    | `--pjx-prompt-dialog-border` | `var(--border)` |
    | `--pjx-prompt-dialog-radius` | `var(--radius-md)` |
    | `--pjx-prompt-dialog-shadow` | `var(--shadow-md)` |
    | `--pjx-prompt-dialog-backdrop` | `rgb(0 0 0 / 0.5)` |

??? note "DOM & classes"

    Root `dialog.pjx-prompt-dialog[data-pjx-dialog="prompt"]` — singleton, matched by `document.querySelector`. Input pre-focused and selected on open.
    API: `pjx.prompt(title, {initial?, placeholder?, okLabel?, cancelLabel?}) → Promise<string | null>`.
    Returns `null` on cancel/Escape/backdrop close. Falls back to `window.prompt` if no `PJXPromptDialog` is mounted.

    **Classes:** `pjx-prompt-dialog`, `pjx-prompt-dialog__card`, `pjx-prompt-dialog__label`, `pjx-prompt-dialog__input`, `pjx-prompt-dialog__actions`, `pjx-prompt-dialog__ok`, `pjx-prompt-dialog__cancel`.

??? note "Python"

    ```python
    PJXPromptDialog(id="demo-prompt")
    ```

### PJXNotification

Fixed-position toast. **Assets:** `pjx_notification.css`, `pjx_notification.js`.

<!-- demo: PJXNotification -->

```html
<PJXNotification
  id="demo-notification"
  content="Your changes have been saved."
  corner="top-right"
  timeout="4000"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `content` | `str \| BaseComponent` | `""` | Message body. |
    | `corner` | literal | `"top-right"` | `top-right`, `top-left`, `bottom-right`, `bottom-left`. |
    | `timeout` | `int` | `5000` | Auto-dismiss ms; `0` disables. Rendered as `data-timeout`. |
    | `autoshow` | `bool` | `True` | When `True`, adds `data-pjx-autoshow`; JS shows the notification as soon as it mounts. |
    | `dismiss_label` | `str` | `"Dismiss"` | `aria-label` for the dismiss button. |

    Maps children to `content`; see the [children-vs-`content` note](#components).

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-notification-width` | `22rem` |
    | `--pjx-notification-gap` | `1.25rem` (viewport inset; used in slide animations) |
    | `--pjx-notification-bg` | `var(--surface-alt)` |
    | `--pjx-notification-border` | `var(--border)` |
    | `--pjx-notification-radius` | `var(--radius-md)` |
    | `--pjx-notification-shadow` | `var(--shadow-md)` |
    | `--pjx-notification-padding` | `1rem 1rem 1rem 1.25rem` |
    | `--pjx-notification-close-color` | `var(--text-muted)` |
    | `--pjx-notification-z` | `500` |

    Content uses `var(--font-size-sm)`, `var(--text)`; close hover uses `var(--surface)`, `var(--text)`, `var(--radius-sm)`, `var(--transition)`.

??? note "DOM & classes"

    Root `.pjx-notification` (state: `.pjx-notification--visible`, `.pjx-notification--hiding`).
    `data-pjx-autoshow` triggers auto-show on mount. `data-pjx-close` inside hides it.
    Events: `pjx:notification:before-show`*, `pjx:notification:show`, `pjx:notification:before-hide`*, `pjx:notification:hide` — `*` = cancelable, `detail = {reason, trigger}`.
    API: `pjx.notification.show(id)`, `pjx.notification.hide(id)`.

    **Classes:** `pjx-notification`; placement `pjx-notification--top-right`, `--top-left`, `--bottom-right`, `--bottom-left`; JS state `pjx-notification--visible`, `pjx-notification--hiding`; `pjx-notification__content`, `pjx-notification__close`.

??? note "Python"

    ```python
    PJXNotification(
        id="demo-notification",
        content="Your changes have been saved.",
        corner="top-right",
        timeout=4000,
    )
    ```

### PJXAlert

Inline status banner. **Assets:** `pjx_alert.css`, `pjx_alert.js`.

<!-- demo: PJXAlert -->

```html
<PJXAlert variant="info" title="Heads up" body="A new version is available."/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `variant` | literal | `"info"` | `info`, `success`, `warning`, `error` → `pjx-alert--{variant}`. |
    | `title` | `str` | `""` | Optional heading. |
    | `body` | `str \| BaseComponent` | `""` | Main copy. |
    | `dismissible` | `bool` | `False` | When `True`, renders a dismiss button with `data-pjx-close`. |
    | `dismiss_label` | `str` | `"Dismiss"` | `aria-label` for the dismiss button. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-alert-radius` | `var(--radius-md)` |
    | `--pjx-alert-padding` | `0.875rem 1rem` |
    | `--pjx-alert-border` | `var(--border)` |
    | `--pjx-alert-shadow` | `var(--shadow-md)` |
    | `--pjx-alert-title-size` | `var(--font-size-sm)` |
    | `--pjx-alert-body-size` | `var(--font-size-sm)` |
    | `--pjx-alert-dismiss-color` | `var(--text-muted)` |

??? note "DOM & classes"

    Root `.pjx-alert` (state: `.pjx-alert--dismissed` — set by JS, hides via `display: none`).
    `data-pjx-close` inside triggers dismissal.
    Events: `pjx:alert:before-dismiss`* (cancelable), `pjx:alert:dismiss` — `detail = {reason: 'trigger', trigger}`.

    **Classes:** `pjx-alert`; variant modifiers `pjx-alert--info`, `--success`, `--warning`, `--error`; dismissed state `pjx-alert--dismissed`; `pjx-alert__inner`, `__text`, `__title`, `__body`, `__dismiss`. Variants use `color-mix` with `--brand`, `--success`, `--warning`, or `--error` / `--error-bg` / `--error-border` where applicable.

??? note "Python"

    ```python
    PJXAlert(variant="info", title="Heads up", body="A new version is available.")
    ```

### PJXTooltip

Composable tooltip shell. Compose with `PJXTooltipTrigger` and `PJXTooltipContent`. **Assets:** `pjx-tooltip.css`, `pjx-tooltip.js` (IIFE — no API, behavior only).

<!-- demo: PJXTooltip -->

```html
<PJXTooltip id="demo-tooltip" placement="top">
  <PJXTooltipTrigger id="demo-tooltip-tr">Hover over me</PJXTooltipTrigger>
  <PJXTooltipContent id="demo-tooltip-tc">This is additional context shown on hover or focus.</PJXTooltipContent>
</PJXTooltip>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `placement` | literal | `"top"` | `top`, `bottom`, `start`, `end` → `data-pjx-tooltip-placement`. |
    | `content` | `str \| BaseComponent` | `""` | Children: compose `PJXTooltipTrigger` + `PJXTooltipContent` here. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-tooltip-gap` | `6px` |
    | `--pjx-tooltip-bg` | `var(--surface-alt)` |
    | `--pjx-tooltip-border` | `var(--border)` |
    | `--pjx-tooltip-radius` | `var(--radius-sm)` |
    | `--pjx-tooltip-shadow` | `var(--shadow-md)` |
    | `--pjx-tooltip-padding` | `0.35rem 0.5rem` |
    | `--pjx-tooltip-max-width` | `20ch` |
    | `--pjx-tooltip-fg` | `var(--text)` |
    | `--pjx-tooltip-font-size` | `var(--font-size-xs)` |
    | `--pjx-tooltip-z` | `400` |

??? note "DOM & classes"

    Root `.pjx-tooltip` `<span>`. `data-pjx-tooltip-placement` drives JS positioning. Tip shows on `mouseover` anywhere inside `.pjx-tooltip` root, or on `focusin` of `.pjx-tooltip__trigger`; hides on `mouseout`/`focusout`; repositions on `scroll`. The JS sets `aria-describedby` at runtime when the tip is shown. No JS API (`pjx._tooltipWired` guard only).

    **Classes:** `pjx-tooltip`.

??? note "Python"

    ```python
    PJXTooltip(
        id="demo-tooltip",
        placement="top",
        content=(
            PJXTooltipTrigger(id="demo-tooltip-tr", content="Hover over me").render()
            + PJXTooltipContent(id="demo-tooltip-tc", content="This is additional context shown on hover or focus.").render()
        ),
    )
    ```

### PJXTooltipTrigger

The focusable trigger part of a tooltip. **Assets:** `pjx-tooltip-trigger.css`.

```html
<PJXTooltipTrigger>Hover over me</PJXTooltipTrigger>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `content` | `str \| BaseComponent` | `""` | Trigger label or element. |

??? note "DOM & classes"

    `<span class="pjx-tooltip__trigger" tabindex="0">`. The JS sets `aria-describedby` to the tip's id at show time. Place inside a `PJXTooltip` shell.

    **Classes:** `pjx-tooltip__trigger`.

??? note "Python"

    ```python
    PJXTooltipTrigger(content="Hover over me")
    ```

### PJXTooltipContent

The floating tip body. **Assets:** `pjx-tooltip-content.css`.

```html
<PJXTooltipContent>This is additional context shown on hover or focus.</PJXTooltipContent>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `content` | `str \| BaseComponent` | `""` | Tooltip text or rich content. |

??? note "DOM & classes"

    `<span class="pjx-tooltip__tip" role="tooltip" hidden>`. The JS removes `hidden` and adds `.pjx-tooltip__tip--visible` on show. Place inside a `PJXTooltip` shell.

    **Classes:** `pjx-tooltip__tip`.

??? note "Python"

    ```python
    PJXTooltipContent(content="This is additional context shown on hover or focus.")
    ```

### PJXPopover

Click-toggle compound. Three separate components; compose them by placing `PJXPopoverTrigger` and `PJXPopoverPanel` **as children inside `PJXPopover`**. **Assets:** `pjx_popover.css`, `pjx_popover.js` (IIFE under `pjx.popover`).

<!-- demo: PJXPopover -->

```html
<PJXPopover id="demo-popover">
  <PJXPopoverTrigger id="demo-popover-t" role="dialog">Show info</PJXPopoverTrigger>
  <PJXPopoverPanel id="demo-popover-p" role="dialog"><strong>Keyboard shortcuts</strong><p style="margin:.35rem 0 0">Press <kbd>?</kbd> anytime to reopen this panel.</p></PJXPopoverPanel>
</PJXPopover>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `content` | `str \| BaseComponent` | `""` | Children (trigger + panel). |
    | `align` | literal | `"start"` | `start` or `end` (panel alignment) → `pjx-popover--align-end`. |
    | `behavior` | `bool` | `True` | When `True`, adds `data-pjx-popover` (JS picks it up). |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-popover-max-width` | `28ch` |
    | `--pjx-popover-bg` | `var(--surface-alt)` |
    | `--pjx-popover-border` | `var(--border)` |
    | `--pjx-popover-radius` | `var(--radius-md)` |
    | `--pjx-popover-shadow` | `var(--shadow-md)` |
    | `--pjx-popover-padding` | `var(--space-3, 0.75rem) var(--space-4, 1rem)` |
    | `--pjx-popover-z` | `300` |

??? note "DOM & classes"

    Root `[data-pjx-popover]` (the PJXPopover wrapper). Trigger: `[data-pjx-toggle]` on the trigger element; `aria-expanded` synced by JS. Panel: `[data-pjx-popover-panel]` element, `hidden` when closed. `data-pjx-close` inside the panel closes it. `data-pjx-toggle="<panel-id>"` on any element opens/closes a named panel.
    Events (bubble from `[data-pjx-popover]`): `pjx:popover:before-open`*, `pjx:popover:open`, `pjx:popover:before-close`*, `pjx:popover:close` — `detail = {reason, trigger}`.
    API: `pjx.popover.open(idOrEl)`, `pjx.popover.close(idOrEl)`, `pjx.popover.toggle(idOrEl)`.

    **Classes:** `pjx-popover`, `pjx-popover--align-end`, `pjx-popover__trigger`, `pjx-popover__panel`.

??? note "Python"

    ```python
    PJXPopover(
        id="demo-popover",
        content=(
            PJXPopoverTrigger(id="demo-popover-t", content="Show info", role="dialog").render()
            + PJXPopoverPanel(
                id="demo-popover-p",
                role="dialog",
                content=(
                    "<strong>Keyboard shortcuts</strong>"
                    '<p style="margin:.35rem 0 0">Press <kbd>?</kbd> anytime to reopen this panel.</p>'
                ),
            ).render()
        ),
    )
    ```

### PJXPopoverTrigger

Trigger button for a `PJXPopover`. **Assets:** bundled in `pjx_popover.css`.

```html
<PJXPopoverTrigger id="t">Open</PJXPopoverTrigger>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `content` | `str \| BaseComponent` | `""` | Button/div label. |
    | `tag` | literal | `"button"` | `button` or `div` (role="button"). |
    | `role` | literal | `""` | `aria-haspopup` value: `menu`, `listbox`, `dialog`, or `""`. |
    | `behavior` | `bool` | `True` | When `True`, adds `data-pjx-toggle`. |

??? note "DOM & classes"

    `[data-pjx-toggle]` element; `aria-expanded` synced by JS.

    **Classes:** `pjx-popover__trigger`.

??? note "Python"

    ```python
    PJXPopoverTrigger(id="t", content="Open")
    ```

### PJXPopoverPanel

Floating panel for a `PJXPopover`. **Assets:** bundled in `pjx_popover.css`.

```html
<PJXPopoverPanel id="p" role="menu">…</PJXPopoverPanel>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `content` | `str \| BaseComponent` | `""` | Panel body. |
    | `as_form` | `bool` | `False` | Render panel as `<form>` instead of `<div>`. |
    | `role` | literal | `""` | ARIA `role` attribute (`menu`, `listbox`, `dialog`, or `""`). |
    | `behavior` | `bool` | `True` | When `True`, adds `data-pjx-popover-panel` (hidden by default). |

??? note "DOM & classes"

    `[data-pjx-popover-panel]` element, `hidden` when closed.

    **Classes:** `pjx-popover__panel`.

??? note "Python"

    ```python
    PJXPopoverPanel(id="p", role="menu", content="…")
    ```

## Interaction & loading

### PJXDropdown

Button + anchored panel backed by the shared popover engine. **Assets:** `pjx_dropdown.css` only (ships no own JS — `pjx_popover.js` is included via the `js` extra-asset field whenever a PJXDropdown renders).

<!-- demo: PJXDropdown -->

```html
<!-- Menu entries are supplied via the `items` prop (a list); see the Python example below. -->
<PJXDropdown trigger="Actions" menu_label="Actions menu" />
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `trigger` | `str \| BaseComponent` | `""` | Button label. |
    | `items` | `list[str \| BaseComponent]` | `[]` | Menu items rendered inside the panel. |
    | `align` | literal | `"start"` | `start` or `end` → `pjx-dropdown--align-end`. |
    | `menu_label` | `str` | `"Submenu"` | `aria-label` on the menu panel. |
    | `behavior` | `bool` | `True` | When `False`, removes all `data-pjx-*` wiring. |

    Trigger id is `{{ id }}-trigger`, menu is `{{ id }}-menu`.

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-dropdown-menu-bg` | `var(--surface-alt)` |
    | `--pjx-dropdown-menu-border` | `var(--border)` |
    | `--pjx-dropdown-menu-radius` | `var(--radius-md)` |
    | `--pjx-dropdown-menu-shadow` | `var(--shadow-md)` |
    | `--pjx-dropdown-menu-padding` | `0.35rem 0` |
    | `--pjx-dropdown-menu-min-w` | `10rem` |
    | `--pjx-dropdown-menu-max-h` | `min(70dvh, 24rem)` |
    | `--pjx-dropdown-z` | `350` |
    | `--pjx-dropdown-trigger-bg` | `var(--surface-alt)` |
    | `--pjx-dropdown-trigger-border` | `var(--border)` |
    | `--pjx-dropdown-trigger-radius` | `var(--radius-md)` |
    | `--pjx-dropdown-trigger-padding` | `0.5rem 0.85rem` |
    | `--pjx-dropdown-trigger-bg-hover` | `color-mix(in srgb, var(--text) 6%, var(--surface-alt))` |

??? note "DOM & classes"

    Root `.pjx-dropdown` with `data-pjx-popover`. Trigger: `button.pjx-dropdown__trigger` with `data-pjx-toggle="{{ id }}-menu"`, `aria-expanded` synced by `pjx_popover.js`. Panel: `div.pjx-dropdown__menu[data-pjx-popover-panel][role="menu"]`, `hidden` when closed. All popover events and API apply: `pjx.popover.open/close/toggle(panelId)`. Document click outside closes the menu; `Escape` closes all open popovers.

    **Classes:** `pjx-dropdown`, `pjx-dropdown--align-end`, `pjx-dropdown__trigger`, `pjx-dropdown__menu`.

??? note "Python"

    ```python
    PJXDropdown(
        trigger="Actions",
        items=[
            "<button>Edit</button>",
            "<button>Duplicate</button>",
            "<button>Delete</button>",
        ],
        menu_label="Actions menu",
    )
    ```

### PJXTabGroup

Thin shell that wraps a composed tab layout. Compose with [`PJXTabList`](#pjxtablist), [`PJXTab`](#pjxtab), and [`PJXTabPanel`](#pjxtabpanel). **Assets:** `pjx-tab-group.css`, `pjx-tab-group.js`.

<!-- demo: PJXTabGroup -->

```html
<PJXTabGroup>
  <PJXTabList>
    <PJXTab id="tg-t0" panel="tg-p0" selected="true">Overview</PJXTab>
    <PJXTab id="tg-t1" panel="tg-p1">Activity</PJXTab>
    <PJXTab id="tg-t2" panel="tg-p2" closeable="true">Settings</PJXTab>
  </PJXTabList>
  <PJXTabPanel id="tg-p0" tab="tg-t0"><p>Project summary and key metrics.</p></PJXTabPanel>
  <PJXTabPanel id="tg-p1" tab="tg-t1"><p>Recent commits and deploys.</p></PJXTabPanel>
  <PJXTabPanel id="tg-p2" tab="tg-t2"><p>Repository configuration.</p></PJXTabPanel>
</PJXTabGroup>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `class_name` | `str` | `""` | Extra CSS class(es) appended to the root element. |
    | `content` | `str \| BaseComponent` | `""` | Composed interior — typically a `PJXTabList` followed by one or more `PJXTabPanel`s. |

    **Panel mode (standalone triggers).** A `PJXTab` rendered *outside* a `PJXTabList` becomes a free-standing trigger: it gets button semantics and an `aria-current` active state instead of the tab strip, and it can live anywhere on the page. It pairs with its region by `panel=` (→ `aria-controls`); the engine resolves the trigger's group through the panel it controls. This replaces the former `PJXPanel`/`PJXPanelTrigger` pair. The `PJXTab` wrapper itself is the interactive element (`role="button"`, `tabindex="0"`), so its content should be inert — plain text or a `<span>` — exactly like list-mode tabs. The engine also backfills `aria-labelledby` on each panel at init from its controlling trigger, so `tab=` on `PJXTabPanel` is not required in panel mode.

    ```html
    <PJXTab panel="files-panel" selected="true">Files</PJXTab>
    <PJXTab panel="chat-panel">Chat</PJXTab>

    <PJXTabGroup id="workspace">
      <PJXTabPanel id="files-panel"><p>Uploaded assets.</p></PJXTabPanel>
      <PJXTabPanel id="chat-panel"><p>Team conversations.</p></PJXTabPanel>
    </PJXTabGroup>
    ```

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-tab-group-border` | `var(--border)` |
    | `--pjx-tab-group-bg` | `var(--surface-alt)` |
    | `--pjx-tab-group-tab-active-fg` | `var(--text)` |
    | `--pjx-tab-group-tab-active-bg` | `color-mix(in srgb, var(--surface) 55%, var(--surface-alt))` |
    | `--pjx-tab-group-tab-active-border` | `var(--brand)` |
    | `--pjx-tab-group-panel-bg` | `var(--surface)` |

??? note "DOM & classes"

    Root `div.pjx-tab-group[data-pjx-tab-group]`. The interior is authored by the caller via `content`. `pjx-tab-group.js` delegates events on `.pjx-tab-group[data-pjx-tab-group]`.

    **Classes:** `pjx-tab-group`.

??? note "Python"

    ```python
    PJXTabGroup(
        content=(
            PJXTabList(content=(
                PJXTab(id="tg-t0", panel="tg-p0", selected=True, content="Overview").render()
                + PJXTab(id="tg-t1", panel="tg-p1", content="Activity").render()
                + PJXTab(id="tg-t2", panel="tg-p2", closeable=True, content="Settings").render()
            )).render()
            + PJXTabPanel(id="tg-p0", tab="tg-t0", content="<p>Project summary and key metrics.</p>").render()
            + PJXTabPanel(id="tg-p1", tab="tg-t1", content="<p>Recent commits and deploys.</p>").render()
            + PJXTabPanel(id="tg-p2", tab="tg-t2", content="<p>Repository configuration.</p>").render()
        ),
    )
    ```

### PJXTabList

Tab button list (the `role="tablist"` container). **Assets:** `pjx-tab-list.css`.

```html
<PJXTabList label="Project tabs">
  <PJXTab id="t0" panel="p0" selected="true">Overview</PJXTab>
  <PJXTab id="t1" panel="p1">Activity</PJXTab>
</PJXTabList>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `label` | `str` | `"Tabs"` | `aria-label` for the tab list — describes the set of tabs. |
    | `class_name` | `str` | `""` | Extra CSS class(es) appended to the root element. |
    | `content` | `str \| BaseComponent` | `""` | One or more `PJXTab` rendered strings. |

??? note "DOM & classes"

    Root `div[role="tablist"][aria-label][aria-orientation="horizontal"].pjx-tab-group__list`.

??? note "Python"

    ```python
    PJXTabList(label="Project tabs", content=PJXTab(id="t0", panel="p0", selected=True, content="Overview").render() + PJXTab(id="t1", panel="p1", content="Activity").render())
    ```

### PJXTab

Single tab button. **Assets:** `pjx-tab.css`.

```html
<PJXTab id="t0" panel="p0" selected="true" icon="file">Overview</PJXTab>
<PJXTab id="t1" panel="p1" closeable="true">Activity</PJXTab>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `panel` | `str` | `""` | `id` of the associated `PJXTabPanel` (`aria-controls`). |
    | `icon` | `str` | `""` | Icon name passed to `PJXIcon`; shown before the label. |
    | `closeable` | `bool` | `False` | Renders a close button (`data-pjx-tab-close`). |
    | `pinned` | `bool` | `False` | Marks the tab as pinned; suppresses close button. |
    | `selected` | `bool` | `False` | Initially selected state (`aria-selected`, `tabindex=0`). |
    | `close_label` | `str` | `"Close"` | `aria-label` for the close button. |
    | `class_name` | `str` | `""` | Extra CSS class(es) appended to the root element. |
    | `content` | `str \| BaseComponent` | `""` | Tab label text or markup. |

??? note "DOM & classes"

    Root `div[role="tab"][data-pjx-tab].pjx-tab`. Selected state adds `pjx-tab--selected`; closeable adds `pjx-tab--closeable`; pinned adds `pjx-tab--pinned`. The `id` here must match the `tab` field on the corresponding `PJXTabPanel`.

??? note "Python"

    ```python
    PJXTab(id="t0", panel="p0", selected=True, icon="file", content="Overview")
    ```

### PJXTabPanel

Panel body associated with one tab. **Assets:** `pjx-tab-panel.css`.

```html
<PJXTabPanel id="p0" tab="t0"><p>Panel content.</p></PJXTabPanel>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `tab` | `str` | `""` | `id` of the owning `PJXTab` (`aria-labelledby`). |
    | `class_name` | `str` | `""` | Extra CSS class(es) appended to the root element. |
    | `content` | `str \| BaseComponent` | `""` | Panel body HTML or component. |

??? note "DOM & classes"

    Root `div[role="tabpanel"][data-pjx-region][hidden].pjx-tab-group__panel`. `hidden` is present on all panels; JS removes it from the selected one. `aria-labelledby` points to the owning tab's `id`.

??? note "Python"

    ```python
    PJXTabPanel(id="p0", tab="t0", content="<p>Panel content.</p>")
    ```

### PJXResizableGroup

Drag-to-resize split-pane container. Compose `PJXResizablePanel` and `PJXResizableHandle` parts inside. **Assets:** `pjx-resizable-group.css`, `pjx-resizable-group.js`.

<!-- demo: PJXResizableGroup -->

```html
<PJXResizableGroup direction="row">
  <PJXResizablePanel size="25" min="15">sidebar</PJXResizablePanel>
  <PJXResizableHandle/>
  <PJXResizablePanel size="75">main</PJXResizablePanel>
</PJXResizableGroup>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `direction` | `"row" \| "column"` | `"row"` | Flex direction for the group (`row` = side-by-side, `column` = stacked). Emits `pjx-resizable-group--row` / `--column` and `data-direction`. |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Pre-rendered children: alternating `PJXResizablePanel` and `PJXResizableHandle` components. |

    **`pjx:resize` event.** Fires on the group root after every drag-end or keyboard step. `detail.sizes` is an ordered array of panel size percentages (one entry per `[data-pjx-resizable-panel]` direct child). Listen to persist the layout:

    ```javascript
    document.addEventListener("pjx:resize", e => {
        localStorage.setItem("panel-sizes", JSON.stringify(e.detail.sizes));
    });
    ```

    **Nesting.** A `PJXResizablePanel` may contain a `PJXResizableGroup` of the perpendicular direction, giving a resizable grid. Each group initializes independently via `:scope` + direct-children traversal.

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-resizable-handle-size` | `0.5rem` |
    | `--pjx-resizable-handle-color` | `transparent` |
    | `--pjx-resizable-grip-color` | `var(--border)` |
    | `--pjx-resizable-handle-color-active` | `var(--brand-muted)` |

??? note "DOM & classes"

    Root `<div role="group" class="pjx-resizable-group pjx-resizable-group--{direction}" data-pjx-resizable-group data-direction="{direction}">` rendering `{{ content }}` verbatim. `pjx-resizable-group.js` initializes on `DOMContentLoaded` and `htmx:afterSettle` (bind-guarded per element), sets `flex-grow` on each panel from the panel's `data-size` attribute, and wires pointer/touch drag and keyboard events to the handles.

    **Classes:** `pjx-resizable-group`; direction modifiers `pjx-resizable-group--row`, `--column`; drag state `pjx-resizable-group--dragging`.

??? note "Python"

    ```python
    PJXResizableGroup(
        id="split",
        direction="row",
        content=(
            PJXResizablePanel(id="split-l", size=25, min=15, content="sidebar").render()
            + PJXResizableHandle(id="split-h").render()
            + PJXResizablePanel(id="split-r", size=75, content="main").render()
        ),
    )
    ```

### PJXResizablePanel

A resizable pane inside a `PJXResizableGroup`. Percentage-sized; `flex-grow` is set from `data-size` by JS. **Assets:** `pjx-resizable-panel.css`.

```html
<PJXResizableGroup direction="row">
  <PJXResizablePanel size="40" min="20">Left panel</PJXResizablePanel>
  <PJXResizableHandle/>
  <PJXResizablePanel size="60">Right panel</PJXResizablePanel>
</PJXResizableGroup>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `size` | `float \| None` | `None` | Initial size as a percentage of the group (e.g. `40` = 40 %). `None` → `flex-grow: 1` (equal share). Rendered as `data-size` and inline `style="flex-grow: {size}"`. |
    | `min` | `str \| float` | `0` | Minimum size. A number = percent of the group; `"120px"` = pixels; `"content"` = the panel's intrinsic min-content (so a fixed child stays visible at any viewport). |
    | `max` | `str \| float` | `100` | Maximum size. A number = percent; `"120px"` = pixels. (`"content"` is not valid for max.) |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) on the root element. |
    | `content` | `str \| BaseComponent` | `""` | Panel body content. |

    Content floor — keeps the bottom strip visible regardless of viewport height:

    ```html
    <PJXResizableGroup direction="column">
      <PJXResizablePanel size="70">messages</PJXResizablePanel>
      <PJXResizableHandle/>
      <PJXResizablePanel size="30" min="content">workspace strip</PJXResizablePanel>
    </PJXResizableGroup>
    ```

??? note "DOM & classes"

    Root `<div class="pjx-resizable-group__panel" data-pjx-resizable-panel [data-size] data-min data-max style="flex-grow: ...">`. Place inside a `PJXResizableGroup`; a `PJXResizableHandle` between two panels enables drag-to-resize. Each panel in the group must be a direct child.

    **Classes:** `pjx-resizable-group__panel`. No own theming tokens; layout is controlled by `flex-grow`.

??? note "Python"

    ```python
    PJXResizablePanel(size=40, min=20, content="Left panel")
    ```

### PJXResizableHandle

The draggable divider between two `PJXResizablePanel` siblings. Keyboard-accessible (`role="separator"`, `tabindex="0"`). **Assets:** `pjx-resizable-handle.css`.

```html
<PJXResizableGroup direction="row">
  <PJXResizablePanel size="50">Left</PJXResizablePanel>
  <PJXResizableHandle label="Resize panels"/>
  <PJXResizablePanel size="50">Right</PJXResizablePanel>
</PJXResizableGroup>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `label` | `str` | `"Resize"` | `aria-label` for the `role="separator"` element. |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) on the root element. |

    **Keyboard controls.** When the handle is focused: `ArrowRight`/`ArrowDown` grows the preceding panel by 5 %; `ArrowLeft`/`ArrowUp` shrinks it by 5 %; `Home` collapses the preceding panel to its `min`; `End` expands it to the remaining group space (clamped to `max`). `min`/`max` constraints from both neighbors are respected.

??? note "DOM & classes"

    Root `<div role="separator" class="pjx-resizable-group__handle" data-pjx-resizable-handle tabindex="0" aria-label="{label}" aria-valuemin="0" aria-valuemax="100">`. Place between two `PJXResizablePanel`s inside a `PJXResizableGroup`. `pjx-resizable-group.js` sets `aria-valuenow` on the preceding panel's size at every update.

    **Classes:** `pjx-resizable-group__handle`. Handle appearance is controlled by the `PJXResizableGroup` style tokens.

??? note "Python"

    ```python
    PJXResizableHandle(label="Resize panels")
    ```

### PJXToastHost

HX-Trigger-driven toast container singleton. Mount once in the layout. **Assets:** `pjx-toast-host.css`, `pjx-toast-host.js`.

<!-- demo: PJXToastHost -->

```html
<PJXToastHost position="bottom-right"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `position` | literal | `"bottom-right"` | `top-right`, `top-left`, `bottom-right`, `bottom-left`. |
    | `timeout` | `int` | `4000` | Default auto-dismiss ms; `0` disables. |
    | `dismiss_label` | `str` | `"Dismiss"` | `aria-label` for dismiss buttons on individual toasts. |
    | `event_name` | `str` | `"pjx:toast"` | Custom event name to listen for (wired on mount). |

    Fire from a FastAPI route via `HX-Trigger`:

    ```python
    import json

    response.headers["HX-Trigger"] = json.dumps({"pjx:toast": {"message": "Saved.", "level": "success"}})
    ```

    Or from JS:

    ```javascript
    pjx.toast("Upload complete.", { level: "success", timeout: 3000 });
    ```

    Toast `level` maps to `.pjx-toast--<level>`; supported values: `info`, `success`, `warning`, `error`.

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-toast-bg` | `var(--surface)` |
    | `--pjx-toast-border` | `var(--border)` |
    | `--pjx-toast-radius` | `var(--radius-md)` |
    | `--pjx-toast-shadow` | `var(--shadow-md)` |
    | `--pjx-toast-gap` | `0.5rem` |
    | `--pjx-toast-z` | `1000` |
    | `--pjx-toast-info` | `var(--brand, #5c8fa8)` |
    | `--pjx-toast-success` | `#3e7d4f` |
    | `--pjx-toast-warning` | `#b07415` |
    | `--pjx-toast-error` | `#b3261e` |

??? note "DOM & classes"

    Root `div.pjx-toast-host[data-pjx-toast-host]`. `data-event-name` sets the custom event; `data-timeout` sets the default dismiss timeout; `data-dismiss-label` sets dismiss button label.
    Events (bubble from the host): `pjx:toasthost:show` (detail: `{level}`), `pjx:toasthost:hide`.
    API: `pjx.toast(message, {level?, timeout?})`.
    Individual toasts: `div.pjx-toast.pjx-toast--<level>` > `.pjx-toast__message` + `button.pjx-toast__dismiss`.

    **Classes:** `pjx-toast-host`, `pjx-toast-host--top-right`, `--top-left`, `--bottom-right`, `--bottom-left`; `pjx-toast`, `pjx-toast--info`, `--success`, `--warning`, `--error`; `pjx-toast--hiding`; `pjx-toast__message`, `pjx-toast__dismiss`.

??? note "Python"

    ```python
    PJXToastHost(position="bottom-right")
    ```

### PJXRegionLoader

In-place loading veil over a positioned ancestor. **Assets:** `pjx-region-loader.css`, `pjx-region-loader.js`.

<!-- demo: PJXRegionLoader -->

```html
<PJXRegionLoader id="demo-region"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `aria_label` | `str` | `"Loading"` | Accessible label (`role="status"`). |

    **Layout:** Overlay is `position: absolute; inset: 0`. Parent must be **`position: relative`** (or any non-`static` value) so coverage is correct.

    Supports both declarative (`hx-indicator`) and programmatic use (`pjx.loader.region.*`).

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-region-loader-bg` | `color-mix(in srgb, var(--text) 55%, transparent)` |
    | `--pjx-region-loader-backdrop` | `blur(2px)` |
    | `--pjx-region-loader-z` | `100` |
    | `--pjx-region-loader-spinner-size` | `2.5rem` |
    | `--pjx-region-loader-spinner-width` | `3px` |
    | `--pjx-region-loader-spinner-color` | `var(--brand)` |
    | `--pjx-region-loader-spinner-track` | `color-mix(in srgb, var(--text) 12%, transparent)` |

??? note "DOM & classes"

    Root `.pjx-region-loader` (state: `.pjx-region-loader--visible`, `.pjx-region-loader--hiding`; also responds to `.htmx-request` as an htmx indicator — CSS activates the veil, no JS call required).
    Events (non-cancelable): `pjx:region-loader:show`, `pjx:region-loader:hide`.
    API: `pjx.loader.region.show/hide/reset(id)` and `pjx.loader.region.wrap(id, promise)`. Ref-counted for concurrent sources: visible from the first `show(id)` to the last `hide(id)`; `show`/`hide` events fire only on real visibility transitions (a show during an in-flight hide cancels it silently); hides finalize via a fallback timer even when animations are disabled. `wrap(id, promise)` pairs show/hide around any async task. Nodes replaced by a swap while sources remain active are re-lit on htmx:afterSettle.

    **Classes:** `pjx-region-loader`; state `pjx-region-loader--visible`, `pjx-region-loader--hiding`; `pjx-region-loader__spinner`.

??? note "Python"

    ```python
    PJXRegionLoader(id="demo-region")
    ```

### PJXPageLoader

Full-page navigation loader. Mount once at the top of the layout body. **Assets:** `pjx-page-loader.css`, `pjx-page-loader.js`.

<!-- demo: PJXPageLoader -->

```html
<PJXPageLoader id="demo-page-loader"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `nav_targets` | `str` | `"app-content"` | Comma-separated element ids whose htmx GET requests activate the loader. |
    | `active_on_load` | `bool` | `True` | When `True`, renders with `.pjx-page-loader--active` (cold-load shimmer, removed on `DOMContentLoaded`). |
    | `loading_label` | `str` | `"Loading"` | `aria-label` for the `role="status"` element. |

    Add `data-pjx-loader` to any element to make its htmx requests activate the loader regardless of `nav_targets`:

    ```html
    <a hx-get="/slow-page" hx-target="#main-content" data-pjx-loader>Go</a>
    ```

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-page-loader-backdrop` | `rgb(0 0 0 / 0.15)` |
    | `--pjx-page-loader-z` | `9999` |
    | `--pjx-page-loader-size` | `2rem` |

??? note "DOM & classes"

    Root `div.pjx-page-loader[data-pjx-page-loader]` (state: `.pjx-page-loader--active`).
    `data-nav-targets` — comma-separated ids; htmx GET requests targeting any of these activate the loader.
    `data-pjx-loader` on any element marks its htmx requests as loader-tracked regardless of target.
    Tracking is detected via `htmx:beforeRequest`; the loader releases via the request's `loadend` (terminal on load, error, abort, and timeout); history navigations reset via `htmx:historyRestore`.
    Events (non-cancelable, bubble from the root): `pjx:page-loader:show`, `pjx:page-loader:hide`.
    API: `pjx.loader.page.show()`, `pjx.loader.page.hide()`, `pjx.loader.page.reset()`, `pjx.loader.page.wrap(promise)`.

    **Classes:** `pjx-page-loader`, `pjx-page-loader--active`, `pjx-page-loader__spinner`.

??? note "Python"

    ```python
    PJXPageLoader(id="demo-page-loader")
    ```

### PJXLazyLoad

HTMX deferred-content loader: an element that fetches `url` on a computed trigger and swaps itself with the response. Use it three ways — a **lazy panel** (load a section's content on first reveal), **load-on-mount**, or an **infinite-scroll sentinel** at the end of a list/table. **Assets:** none. `PJXLazyLoad` needs a backend, so it has no live render.

```html
<PJXLazyLoad id="comments" url="/posts/42/comments">
  <PJXSkeleton id="comments-skel"/>
</PJXLazyLoad>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `url` | `str` | required | Endpoint for the deferred content (`hx-get`). |
    | `when` | literal | `"viewport"` | `viewport` (scroll-revealed), `reveal` (`pjx:reveal` from nearest `[data-pjx-region]`), `load` (immediately). Overridden by `trigger`. |
    | `trigger` | `str` | `""` | Explicit `hx-trigger` value; overrides `when` entirely when set. |
    | `swap` | `str` | `"outerHTML"` | `hx-swap` strategy. The default self-replaces the element. |
    | `tag` | literal | `"div"` | Rendered root element: `div`, `li` (inside a `<ul>`/`<ol>`), or `tr` (inside a `<tbody>`). Lets the loader sit directly in a list or table. |
    | `content` | `str \| BaseComponent` | `""` | Placeholder / loading indicator shown until the fetch lands (e.g. a [`PJXSkeleton`](#pjxskeleton) or "Loading…"). |

    `when` preset mapping:

    | `when` | `hx-trigger` value |
    | --- | --- |
    | `viewport` (default) | `revealed` |
    | `reveal` | `pjx:reveal from:closest [data-pjx-region] once` |
    | `load` | `load` |

    **Load more on scroll (infinite-scroll sentinel).** Drop a `PJXLazyLoad` at the end of a list or `<tbody>` with `when="viewport"` and the matching `tag`. When it scrolls into view it `hx-get`s `url` and `outerHTML`-replaces itself with the server's next batch **plus a fresh `PJXLazyLoad`** carrying the next cursor; the loop ends when the server stops emitting a sentinel. The scroll container is just a `max-height; overflow:auto` wrapper (or the page) — no extra component needed. Ships no JS (htmx's `revealed` does the visibility detection).

    ```html
    <tbody id="rows">
      <!-- … rendered rows … -->
      <PJXLazyLoad url="/rows?cursor=20" tag="tr" content="Loading…"/>
    </tbody>
    ```

??? note "DOM & classes"

    Root `.pjx-lazy-load` (element chosen by `tag`); no JS (pure HTMX). `data-pjx-region` on a `PJXTabPanel` host fires `pjx:reveal`/`pjx:before-reveal` events that `when="reveal"` listens for.

    **Classes:** `pjx-lazy-load` (unstyled hook). No theming tokens.

??? note "Python"

    ```python
    PJXLazyLoad(id="comments", url="/posts/42/comments", content=PJXSkeleton(id="comments-skel"))
    ```

## Form controls

### PJXChipInput

Tag-style multi-value input. Each chip carries its own `<input type="hidden">` so values post with any enclosing form and removal is pure DOM removal. **Assets:** `pjx-chip-input.css`, `pjx-chip-input.js`.

<!-- demo: PJXChipInput -->

```html
<PJXChipInput name="tags" values='["python", "jinja2", "htmx"]' placeholder="Add tag…"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `name` | `str` | — | `name` attribute on the hidden inputs and the `data-name` data attribute. |
    | `values` | `list[str]` | `[]` | Initial chip values. |
    | `placeholder` | `str` | `"Add…"` | Placeholder text in the text field. |
    | `remove_label` | `str` | `"Remove"` | `aria-label` on every remove button; also stored as `data-remove-label` so JS can copy it into dynamically built chips. |
    | `disabled` | `bool` | `False` | When `True`, no text field or remove buttons are rendered; `data-disabled` is set on the root. |

    **Notes:**

    - `values` are plain-text chip labels and are **HTML-escaped** on render (output is escaped by default — see [Escaping & slots](guide/components.md#escaping-and-slots)). Passing markup shows it as literal text, not HTML.
    - Duplicate entries are silently dropped (the field clears).
    - Chips added client-side exist only in the DOM until the form posts; an htmx swap of the surrounding region re-renders from server state.

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-chip-input-gap` | `0.375rem` |
    | `--pjx-chip-input-chip-bg` | `var(--surface-alt)` |
    | `--pjx-chip-input-chip-fg` | `var(--text)` |
    | `--pjx-chip-input-chip-radius` | `var(--radius-full)` |
    | `--pjx-chip-input-border` | `var(--border)` |
    | `--pjx-chip-input-focus` | `var(--border-focus, var(--border))` |
    | `--pjx-chip-input-radius` | `var(--radius-md)` |
    | `--pjx-chip-input-padding` | `0.375rem 0.5rem` |

??? note "DOM & classes"

    Root `div.pjx-chip-input[data-pjx-chip-input][data-name][data-remove-label]`; state: `[data-disabled]`.
    Each chip: `span.pjx-chip-input__chip[data-pjx-chip]` containing a `.pjx-chip-input__label`, `input[type=hidden]`, and (when enabled) `button.pjx-chip-input__remove[data-pjx-chip-remove]`.
    Text field: `input.pjx-chip-input__field`.
    Events (bubble from root): `pjx:chip-input:before-add`* (detail `{value}`), `pjx:chip-input:add`, `pjx:chip-input:before-remove`* (detail `{value}`), `pjx:chip-input:remove` — `*` = cancelable. Commit triggers: `Enter`, `,`, `focusout`, `submit` (form submit commits pending text); Backspace on empty field removes the last chip.

    **Classes:** `pjx-chip-input`, `pjx-chip-input__chip`, `pjx-chip-input__label`, `pjx-chip-input__remove`, `pjx-chip-input__field`.

??? note "Python"

    ```python
    PJXChipInput(
        name="tags",
        values=["python", "jinja2", "htmx"],
        placeholder="Add tag…",
    )
    ```

### PJXFormField

Labelled control wrapper with help text and error state. **Assets:** `pjx-form-field.css` only.

<!-- demo: PJXFormField -->

```html
<PJXFormField label="Email address" for_id="demo-email" help="We'll never share your email with anyone." required="true">
  <input id="demo-email" type="email" name="email" placeholder="you@example.com">
</PJXFormField>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `label` | `str` | `""` | Label text; renders `<label>` only when non-empty. |
    | `for_id` | `str` | `""` | When set, adds `for="{{ for_id }}"` to the label. |
    | `content` | `str \| BaseComponent` | `""` | Control HTML (an `<input>`, `<select>`, etc.). |
    | `help` | `str` | `""` | Help text shown below the control — suppressed when `error` is set. |
    | `error` | `str` | `""` | Error message; adds `pjx-form-field--error` to the root and a `role="alert"` paragraph with id `{{ id }}-error`. |
    | `required` | `bool` | `False` | Renders a `<span class="pjx-form-field__required" aria-hidden="true">*</span>` inside the label. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-form-field-gap` | `0.375rem` |
    | `--pjx-form-field-label-size` | `0.875em` |
    | `--pjx-form-field-label-color` | `var(--text)` |
    | `--pjx-form-field-help-color` | `var(--text-muted)` |
    | `--pjx-form-field-error` | `#b3261e` |

??? note "DOM & classes"

    Root `div.pjx-form-field`; error state `div.pjx-form-field--error`. Help paragraph id: `{{ id }}-help`. Error paragraph id: `{{ id }}-error`, `role="alert"`. No JS.

    **Classes:** `pjx-form-field`, `pjx-form-field--error`, `pjx-form-field__label`, `pjx-form-field__required`, `pjx-form-field__control`, `pjx-form-field__help`, `pjx-form-field__error`.

??? note "Python"

    ```python
    PJXFormField(
        label="Email address",
        for_id="demo-email",
        content='<input id="demo-email" type="email" name="email" placeholder="you@example.com">',
        help="We'll never share your email with anyone.",
        required=True,
    )
    ```

### PJXToggleSwitch

Accessible on/off toggle backed by a visually-hidden checkbox. **Assets:** `pjx-toggle-switch.css` only — no JS.

<!-- demo: PJXToggleSwitch -->

```html
<PJXToggleSwitch name="notifications" checked="true" label="Email notifications"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `name` | `str` | `""` | `name` attribute on the hidden checkbox. |
    | `value` | `str` | `"on"` | `value` attribute on the checkbox. |
    | `checked` | `bool` | `False` | When `True`, adds `checked` to the checkbox. |
    | `label` | `str` | `""` | Visible label text rendered after the track; omitted when empty. |
    | `disabled` | `bool` | `False` | When `True`, adds `disabled` to the checkbox. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-toggle-switch-width` | `2.75rem` |
    | `--pjx-toggle-switch-height` | `1.5rem` |
    | `--pjx-toggle-switch-track` | `var(--border)` |
    | `--pjx-toggle-switch-track-on` | `var(--brand)` |
    | `--pjx-toggle-switch-thumb` | `#fff` |
    | `--pjx-toggle-switch-radius` | `var(--radius-full)` |
    | `--pjx-toggle-switch-gap` | `0.5rem` |

??? note "DOM & classes"

    Root `label.pjx-toggle-switch` wrapping a visually-hidden `input[type=checkbox].pjx-toggle-switch__input` (uses `clip-path: inset(50%)`, not `display:none` — keeps focus and click). CSS keys on `:checked + .pjx-toggle-switch__track` for the active state and `:focus-visible + .pjx-toggle-switch__track` for the ring. No JS API.

    **Classes:** `pjx-toggle-switch`, `pjx-toggle-switch__input`, `pjx-toggle-switch__track`, `pjx-toggle-switch__thumb`, `pjx-toggle-switch__label`.

??? note "Python"

    ```python
    PJXToggleSwitch(name="notifications", checked=True, label="Email notifications")
    ```

### PJXSegmentedControl

Pill-style radio group for mutually exclusive options. **Assets:** `pjx-segmented-control.css` only — no JS.

<!-- demo: PJXSegmentedControl -->

```html
<PJXSegmentedControl name="view" options='[["list", "List"], ["grid", "Grid"], ["table", "Table"]]' selected="grid"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `name` | `str` | — | `name` on all radio inputs. |
    | `options` | `list[tuple[str, str]]` | `[]` | `(value, label)` pairs. Also accepts a JSON string when passed as a tag attribute. |
    | `selected` | `str` | `""` | Value of the pre-checked option. |
    | `disabled` | `bool` | `False` | When `True`, adds `disabled` to all radio inputs. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-segmented-control-bg` | `var(--surface-alt)` |
    | `--pjx-segmented-control-border` | `var(--border)` |
    | `--pjx-segmented-control-radius` | `var(--radius-full)` |
    | `--pjx-segmented-control-gap` | `0.25rem` |
    | `--pjx-segmented-control-padding` | `0.25rem` |
    | `--pjx-segmented-control-active-bg` | `var(--surface)` |
    | `--pjx-segmented-control-active-fg` | `var(--text)` |
    | `--pjx-segmented-control-active-shadow` | `0 1px 3px rgb(0 0 0 / 0.12)` |
    | `--pjx-segmented-control-fg` | `var(--text-muted)` |
    | `--pjx-segmented-control-focus` | `var(--border-focus, var(--brand))` |

??? note "DOM & classes"

    Root `div.pjx-segmented-control[role="radiogroup"]`. Each option: `label.pjx-segmented-control__segment` > `input[type=radio].pjx-segmented-control__input` (visually hidden, `clip-path: inset(50%)`) + `span.pjx-segmented-control__text`. CSS keys on `:checked + .pjx-segmented-control__text` for the active segment. No JS API.

    **Classes:** `pjx-segmented-control`, `pjx-segmented-control__segment`, `pjx-segmented-control__input`, `pjx-segmented-control__text`.

??? note "Python"

    ```python
    PJXSegmentedControl(
        name="view",
        options=[("list", "List"), ("grid", "Grid"), ("table", "Table")],
        selected="grid",
    )
    ```

### PJXPasswordInput

Password field with a show/hide toggle button. **Assets:** `pjx-password-input.css`, `pjx-password-input.js`.

<!-- demo: PJXPasswordInput -->

```html
<PJXPasswordInput name="password" placeholder="Enter your password" autocomplete="current-password" required="true"/>
```

??? note "Props & API"

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `name` | `str` | `"password"` | `name` on the `<input>`. |
    | `placeholder` | `str` | `""` | `placeholder` on the `<input>`; omitted when empty. |
    | `autocomplete` | `str` | `"current-password"` | `autocomplete` attribute. |
    | `required` | `bool` | `False` | When `True`, adds `required` to the `<input>`. |
    | `show_label` | `str` | `"Show password"` | Static `aria-label` on the toggle button; visibility state is conveyed by `aria-pressed` (ARIA toggle-button pattern). |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-password-input-border` | `var(--border)` |
    | `--pjx-password-input-radius` | `var(--radius-md)` |
    | `--pjx-password-input-focus` | `var(--border-focus, var(--brand))` |
    | `--pjx-password-input-toggle-color` | `var(--text-muted)` |
    | `--pjx-password-input-eye-size` | `1.25rem` |

??? note "DOM & classes"

    Root `div.pjx-password-input[data-pjx-password]`. Field: `input.pjx-password-input__field` with id `{{ id }}-field`. Toggle button: `button.pjx-password-input__toggle[data-pjx-password-toggle]`; `aria-pressed` reflects state (`"false"` when hidden, `"true"` when shown); `.pjx-password-input__toggle--on` class added when visible. No `pjx:*` events — state is readable from `aria-pressed` on the button. No JS API under `window.pjx`.

    **Classes:** `pjx-password-input`, `pjx-password-input__field`, `pjx-password-input__toggle`, `pjx-password-input__toggle--on`, `pjx-password-input__eye`.

??? note "Python"

    ```python
    PJXPasswordInput(
        name="password",
        placeholder="Enter your password",
        autocomplete="current-password",
        required=True,
    )
    ```

### PJXPaginator

Accessible page-navigation bar. **Assets:** `pjx-paginator.css` only.

<!-- demo: PJXPaginator -->

```html
<PJXPaginator page="4" total_pages="12" url="/items?page={page}"/>
```

??? note "Props & API"

    Pairs naturally with [`PJXTable`](#pjxtable): point `target` at the table body or its wrapper and return the re-paged fragment from your view to update both the rows and the paginator in one swap.

    | Field | Type | Default | Description |
    | --- | --- | --- | --- |
    | `page` | `int` | *(required)* | Current page number (clamped to `[1, total_pages]` internally). |
    | `total_pages` | `int` | *(required)* | Total number of pages (must be ≥ 1). |
    | `url` | `str` | *(required)* | URL template; **must contain `{page}`** (e.g. `/items?page={page}`). |
    | `target` | `str` | `""` | CSS selector for the htmx swap target. When set, every link gets `hx-get`/`hx-target`/`hx-swap` (and `hx-push-url` when `push_url=True`); when empty, links render as plain `<a href>`. |
    | `swap` | `str` | `"innerHTML"` | htmx `hx-swap` strategy; only used when `target` is set. |
    | `push_url` | `bool` | `False` | When `True` and `target` is set, adds `hx-push-url="true"` to each link. |
    | `siblings` | `int` | `1` | Pages shown on each side of the current page (≥ 0). |
    | `boundaries` | `int` | `1` | Pages shown at each end of the range (≥ 0). |
    | `prev_next` | `bool` | `True` | Render Prev / Next controls. |
    | `first_last` | `bool` | `False` | Render First / Last controls. |
    | `prev_label` | `str` | `"Prev"` | Label for the Prev control. |
    | `next_label` | `str` | `"Next"` | Label for the Next control. |
    | `first_label` | `str` | `"First"` | Label for the First control. |
    | `last_label` | `str` | `"Last"` | Label for the Last control. |
    | `aria_label` | `str` | `"Pagination"` | `aria-label` on the root `<nav>`. |
    | `class_name` | `AttrValue` | `""` | Extra CSS class(es) on the root element. |

??? note "Style tokens"

    | Token | Default |
    | --- | --- |
    | `--pjx-paginator-gap` | `0.25rem` |
    | `--pjx-paginator-link-fg` | `var(--text)` |
    | `--pjx-paginator-link-bg` | `transparent` |
    | `--pjx-paginator-link-hover-bg` | `var(--surface-alt)` |
    | `--pjx-paginator-current-fg` | `var(--brand)` |
    | `--pjx-paginator-current-bg` | `var(--brand-subtle)` |
    | `--pjx-paginator-border` | `var(--border)` |
    | `--pjx-paginator-radius` | `var(--radius-sm)` |
    | `--pjx-paginator-disabled-opacity` | `0.4` |

??? note "DOM & classes"

    Root `<nav class="pjx-paginator" aria-label="...">` containing `<ul class="pjx-paginator__list">` → `<li class="pjx-paginator__item">` per entry. The current page renders as `<span class="pjx-paginator__link pjx-paginator__link--current" aria-current="page">`. Ellipsis gaps render as `<span class="pjx-paginator__ellipsis" aria-hidden="true">`. Disabled controls (Prev on page 1, Next on the last page, etc.) render as `<span class="pjx-paginator__control pjx-paginator__control--{variant} pjx-paginator__control--disabled" aria-disabled="true">`. Each active page link and enabled control renders as `<a href="...">` when `target` is empty, or as `<a hx-get="..." hx-target="..." hx-swap="...">` when `target` is set. No JS.

    **Classes:** `pjx-paginator`, `pjx-paginator__list`, `pjx-paginator__item`, `pjx-paginator__link`, `pjx-paginator__link--current`, `pjx-paginator__ellipsis`, `pjx-paginator__control`, `pjx-paginator__control--first`, `pjx-paginator__control--prev`, `pjx-paginator__control--next`, `pjx-paginator__control--last`, `pjx-paginator__control--disabled`.

??? note "Python"

    ```python
    PJXPaginator(page=4, total_pages=12, url="/items?page={page}", target="#list")
    ```
```