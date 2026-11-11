# ADR 0007: Opt-in default theme with grouped `--pjx-*` tokens

**Status:** Accepted, 2026-11-11. Unreleased.

## Context

Builtin CSS reads about twenty unprefixed theme variables (`--surface`,
`--text`, `--border`, `--brand`, `--radius-md`, …) in about 300 places, with
no fallback. pyjinhx defines none of them. Only the docs gallery's
`docs/demos/base.css` does, so an app that does not define them gets builtins
with missing colours and borders. Two of the names in use, `--surface-hover`
and `--space-2`, are defined nowhere at all.

The scales that exist are thin: three font sizes, two spacing steps, one
shadow, one transition. There is no dark mode. The status colours are uneven,
with no `info`. Z-index values are scattered from 100 to 9999 across eleven
per-component tokens. There is no chart palette, no layout piece and no
theming documentation.

## Decision: grouped `--pjx-*` names, and the old names are dropped

Theme tokens are grouped by kind and carry the library's prefix:
`--pjx-color-*`, `--pjx-font-*`, `--pjx-line-height-*`, `--pjx-space-*`,
`--pjx-radius-*`, `--pjx-shadow-*`, `--pjx-duration-*`, `--pjx-easing-*`,
`--pjx-z-*` and `--pjx-chart-series-N`. Component tokens such as
`--pjx-button-bg` keep the names they have.

The prefix matters because an app's own CSS is likely to define `--surface`
or `--text` for its own purposes, and a builtin would silently pick those up.
The unprefixed names are dropped now, with no fallback chain to them.

## Decision: opt-in, and emitted before everything else

The theme is off unless asked for: `PjxSettings(theme="default")`, with
`None` as the default, or the `PJX_THEME` environment variable. When it is
on, `inject_runtime` puts `<style id="pjx-theme">` before `pjx-style` and
before all builtin CSS. Apps that build their own `<head>` get the same sheet
from `pyjinhx.client.read_pjx_theme_css()` or `PJX_THEME_PATH`, which read
`pyjinhx/client/pjx_theme.css`.

The theme only defines variables, so it goes first. Any later rule, from a
builtin or from the app, can override it. That is the same origin ordering
[ADR 0003](0003-builtin-css-ordering.md) set for builtin and app CSS: the
more general layer emits earlier.

## Decision: literal light fallbacks, shipped in a minor release

Every theme-token reference in builtin CSS carries a literal fallback equal
to the theme's light value, for example `var(--pjx-color-surface, #ffffff)`.
With no theme, builtins still look right. A test checks that each fallback
matches the sheet's light value, so the two cannot drift apart.

The change ships as a minor release, with a prominent CHANGELOG migration
notice and an old → new mapping table. The old names were never part of
pyjinhx's published surface: only the gallery defined them.

## Decision: dark mode follows the OS, and an attribute forces either

The theme follows `prefers-color-scheme`. Setting `data-pjx-theme="light"`
or `data-pjx-theme="dark"` on `<html>` or on any wrapper forces one mode for
that subtree.

The sheet puts constants and light values on `:root`. Dark values sit under
`@media (prefers-color-scheme: dark)` on `:root:not([data-pjx-theme="light"])`,
and again under `[data-pjx-theme="dark"]`. Light values are re-asserted under
`[data-pjx-theme="light"]`, so a light wrapper inside a dark page works.

## Decision: typography classes and one layout builtin

Typography is a set of CSS classes, not components: `.pjx-heading-1` to
`.pjx-heading-4`, `.pjx-text-lg`, `.pjx-text`, `.pjx-text-sm`,
`.pjx-text-muted`, `.pjx-text-mono` and `.pjx-caption`. They ship in the
theme sheet. Layout gets one new builtin, `PJXStack`, with a direction, a
gap from the spacing scale, `align`, `justify` and `wrap`.

Breakpoints are a documented scale, not tokens: sm 640px, md 768px, lg
1024px, xl 1280px. CSS variables cannot be used in `@media` conditions, so a
token would not help. Builtin CSS that needs a breakpoint uses these values.

## Decision: the look

- **Brand: Graphite.** Monochrome, with the zinc neutral as the brand: light
  `#27272a`, dark `#e4e4e7`.
- **Neutrals: zinc.**
- **Corners: soft.** `--pjx-radius-sm`, `-md` and `-lg` are 4, 8 and 12px,
  and `--pjx-radius-full` is 9999px. These are today's values, so corners do
  not change.
- **Chart series: colour-blind safe.** `--pjx-chart-series-1` to `-8` are the
  palette `PJXChart` already validated for colour-vision deficiency and
  contrast, with light and dark steps.

## Rejected: keeping the old names, or a fallback chain to them

The unprefixed names collide with variables an app defines for itself, and
pyjinhx never shipped them, so there is no published name to preserve. A
chain such as `var(--pjx-color-surface, var(--surface, #fff))` would keep old
setups working, but it doubles every reference and keeps the old names alive
with no end date.

## Rejected: an always-on theme

It would change the look of every existing app and fight the token
definitions those apps already have.

## Rejected: no fallbacks, or a major version bump

A bare `var()` with no fallback is today's broken state: with no theme,
builtins lose their colours and borders. A major release would signal a
break in the published API, but the names being removed were never part of
it.

## Rejected: a toggle attribute with no OS preference

An attribute alone would leave every app in light mode until it wrote its
own toggle. Following the OS gives dark mode for free.

## Rejected: typography components, more layouts, breakpoint tokens

A component per text style would wrap every heading in a render for no
behaviour; a class does the same job. `PJXGrid`, `PJXContainer` and
`PJXCluster` are left for later; `PJXStack` covers the common case now.
Breakpoint tokens cannot be read in `@media`, and a helper API is more
surface than a four-step scale needs.

## Rejected: a coloured brand, or a palette picked for looks

A coloured default is one every app would have to override to look like
itself; a monochrome brand stays out of the way. A chart palette chosen
without the colour-vision and contrast check would leave some readers unable
to tell series apart.

## Consequences

- Apps that defined the old unprefixed names for builtins must rename them.
  The CHANGELOG carries the mapping table.
- With no theme, builtins render with the light fallbacks. Dark mode needs
  the theme, or the app's own `--pjx-*` values.
- Every theme-token reference in builtin CSS must carry the light fallback.
  A guard test enforces it once the builtins have moved to the new names.
- Component `-z` tokens default to the layer scale but stay overridable.
- `PJXChart` landed as it is ([ADR 0006](0006-server-rendered-svg-charts.md)).
  In the builtin migration, `--pjx-chart-N` defaults to
  `--pjx-chart-series-N`, and its dark-mode switch moves from `data-theme`
  to `data-pjx-theme`.
- The change ships in stages: the sheet, its delivery and the guard test
  first, then the builtin migration, then the new pieces, then the docs.
- Exact token values live in the sheet and may still be tuned before release.
- Left for later: Grid, Container and Cluster layouts, typography
  components, brand themes beyond the default, density modes and a
  breakpoint API.

## Related

- [ADR 0003](0003-builtin-css-ordering.md): why emitting the theme before
  builtin CSS fits the origin ordering.
- [ADR 0006](0006-server-rendered-svg-charts.md): the chart and its
  validated palette.
- [Configuration](../guide/configuration.md): `PjxSettings` and environment
  variables.
- [Builtin conventions](../guide/builtin-conventions.md): the contract every
  builtin follows.
