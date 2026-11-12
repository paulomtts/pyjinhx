# Theming

The default theme is one stylesheet of `--pjx-*` CSS variables, plus a few typography classes.
Every builtin reads its colours, spacing, corners, shadows and timing from those variables, so
changing a variable re-skins every component that uses it. The theme is **off by default**: an app
that does not ask for it renders exactly as before.
[ADR 0007](../decisions/0007-default-theme.md) records why it is opt-in and how the tokens are
named.

## Quick start

Pass `theme="default"` to `setup()`. Keywords merge into the settings, so this is the same as
passing a settings object:

```python
from fastapi import FastAPI

from pyjinhx import PjxSettings, setup

app = FastAPI()
setup(app, theme="default")
# or, the same thing:
# setup(app, settings=PjxSettings(theme="default"))
```

Or set it from the environment with `PJX_THEME=default` and `PjxSettings.from_env()`:

```python
setup(app, settings=PjxSettings.from_env())
```

`PJX_THEME` unset or empty means no theme. Any other value raises `ValueError` when the settings
are built, including `Default` or `DEFAULT`: the match is exact, because a near miss is more
likely a typo than a request for the theme. See [Configuration](configuration.md) for the other
settings.

With the theme on, a cold full-page render puts `<style id="pjx-theme">` first in the page,
before `<style id="pjx-style">` and before any builtin CSS, so everything after it can read the
tokens and override them. The sheet is part of the runtime injection, so htmx and reactive partial
responses never carry it: it arrives with the first full page, and every partial after that is
swapped into a page that already has it. If you expect to see it in a partial response, it will
not be there.

### Building your own `<head>`

If your app writes its own `<head>` instead of letting pyjinhx inject, read the sheet yourself.
Put it ahead of your other CSS so your rules can override it:

```python
from pyjinhx.client import PJX_THEME_PATH, read_pjx_theme_css

head = f'<style id="pjx-theme">{read_pjx_theme_css()}</style><link rel="stylesheet" href="/app.css">'
```

Or serve the file at `PJX_THEME_PATH` as a static asset and link it first.

### Without the theme

Builtins still render without it. Every token reference in builtin CSS carries the light value
as a literal fallback, such as `var(--pjx-color-border, #e4e4e7)`, so you get the light look.
What you do not get is dark mode: that lives in the theme sheet, unless your app defines the
`--pjx-*` values itself.

## Dark mode

The theme follows the operating system's `prefers-color-scheme` on its own. To force a mode, set
`data-pjx-theme="dark"` or `data-pjx-theme="light"` on `<html>`:

```html
<html data-pjx-theme="dark">
```

A toggle is one line of JavaScript:

```js
document.documentElement.dataset.pjxTheme = "dark"; // or "light"
```

Only colours, chart series and shadows change between the two modes. The type, spacing, radius,
duration, easing and z-index scales are the same in both.

The attribute also works on any element, and forces the theme tokens for that subtree: a light
panel inside a dark page, or the reverse. That reaches anything that reads a theme token directly,
such as the typography classes, your own CSS, and the builtin rules that read a theme token
directly. Builtins with component tokens are different. They declare those
tokens once, in a `:where(:root)` block, and a CSS variable that reads another variable is
resolved where it is declared. So a badge inside a `data-pjx-theme="dark"` panel keeps the
colours its tokens got at the root. To flip a builtin inside a wrapper, set its component tokens
on the wrapper too (see [Component tokens and theme tokens](#component-tokens-and-theme-tokens)).
For a whole page, put the attribute on `<html>`, where everything follows it.

`PJXChart` follows the same attribute on `<html>` (it used to read `data-theme`). The chart sets
its own dark series colours, `--pjx-chart-1` to `--pjx-chart-8`, so to recolour a series in both
modes override those, not the theme's series tokens. See [Chart theming](chart.md#theming).

## Overriding tokens

The theme is emitted first, so a rule in your stylesheet with the same selector wins. To change a
token everywhere, set it on `:root`:

```css
:root { --pjx-color-brand: #4f46e5; }
```

That alone is lost in dark mode. The sheet's dark values sit on
`:root:not([data-pjx-theme="light"])` inside `@media (prefers-color-scheme: dark)`, which is more
specific than `:root`, so it beats your rule whenever the system is dark. Override a colour in
both modes with all four rules, at the top level of your stylesheet, in this order:

```css
:root { --pjx-color-brand: #4f46e5; }
@media (prefers-color-scheme: dark) {
  :root:not([data-pjx-theme="light"]) { --pjx-color-brand: #a5b4fc; }
}
[data-pjx-theme="dark"] { --pjx-color-brand: #a5b4fc; }
[data-pjx-theme="light"] { --pjx-color-brand: #4f46e5; }
```

The light value comes first. The forced-dark rule comes after `:root`, so
`<html data-pjx-theme="dark">` gets the dark value. The forced-light rule comes last, so a light
wrapper inside a dark page gets the light value. Tokens that do not change between modes, such as
spacing or radius, need only the `:root` rule.

You can also set tokens on any class or element, and they apply to everything under it that reads
them directly:

```css
.marketing { --pjx-radius-md: 0; }
```

As with dark mode, builtins with component tokens under that wrapper keep the values those tokens
got at the root; set the component tokens on the wrapper to change them.

The theme tokens come in these groups:

- `--pjx-color-*` — surfaces, borders, text, brand, focus, and the info, success, warning and error status colours
- `--pjx-font-*` — font families, sizes and weights
- `--pjx-line-height-*` — tight, normal and relaxed
- `--pjx-space-*` — the spacing scale
- `--pjx-radius-*` — corner radii
- `--pjx-shadow-*` — elevation shadows
- `--pjx-duration-*` — transition durations
- `--pjx-easing-*` — transition curves
- `--pjx-z-*` — the stacking scale, from raised content up to the page loader
- `--pjx-chart-series-N` — the eight chart series colours

The [token reference](../reference/theme-tokens.md) lists every token with its light and dark value.

## Mapping your design system

If your app already has its own CSS variables, point the `--pjx-*` tokens at them:

```css
:root {
  --pjx-color-brand: var(--my-primary);
  --pjx-color-surface: var(--my-bg);
}
```

This works with or without `theme="default"`. Without the theme, every token you do not map falls
back to the light literal in the builtin's CSS. With the theme, every token you do not map gets
the theme's value, dark mode included. If your design system has its own dark mode, map the tokens
again inside its dark selector the same way.

## Typography

The theme sheet ships these classes, so they need `theme="default"` or the sheet in your own
`<head>`:

- `.pjx-heading-1`, `.pjx-heading-2`, `.pjx-heading-3`, `.pjx-heading-4` — headings, largest first
- `.pjx-text-lg`, `.pjx-text`, `.pjx-text-sm` — body text sizes
- `.pjx-caption` — small, muted text
- `.pjx-text-muted` — muted colour only, to combine with a size class
- `.pjx-text-mono` — the monospace family only, to combine with a size class

```html
<h2 class="pjx-heading-2">Billing</h2>
<p class="pjx-text">Your plan renews on the 1st.</p>
<p class="pjx-text-sm pjx-text-muted">Prices include tax.</p>
```

## Breakpoints

| Name | Width |
| --- | --- |
| sm | 640px |
| md | 768px |
| lg | 1024px |
| xl | 1280px |

The breakpoints are a documented scale, not tokens: CSS variables cannot be used in `@media`
conditions, so a token would not help. Builtin CSS that needs a breakpoint uses these values;
use them in your own media queries so your layout changes at the same widths:

```css
@media (min-width: 768px) {
  .sidebar { display: block; }
}
```

## Component tokens and theme tokens

Many builtins also have their own component tokens, such as `--pjx-badge-bg`,
`--pjx-paginator-border` and `--pjx-page-loader-z`. They are declared in the builtin's CSS in a
`:where(:root)` block, which has no specificity, and each default reads a theme token with a
literal fallback:

```css
--pjx-paginator-border: var(--pjx-color-border, #e4e4e7);
--pjx-page-loader-z:        var(--pjx-z-page-loader, 1000);
```

The rule of thumb:

- To re-skin everything, change a theme token, such as `--pjx-color-border`.
- To change one component, set its component token, on the component's class or on a wrapper:

```css
.pjx-paginator { --pjx-paginator-border: #4f46e5; }
.dark-panel { --pjx-badge-bg: #27272a; --pjx-badge-text: #f4f4f5; }
```

Setting a component token on a wrapper is also how a builtin inside a `data-pjx-theme` or token
wrapper picks up that wrapper's look.
