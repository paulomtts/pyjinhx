# ADR 0008: Graph edge kinds live on ports; wires are steered by cancelable events

**Status:** Proposed, 2026-11-21. Unreleased.

## Context

The graph engine drew one family of edges: out of a right-hand out-port,
into the middle of the target's left edge, along a horizontal curve. It
reported a landed wire as `pjx:graph:wire` and nothing else, so an app could
only refuse a bad connection after the user had made it.

Apps building flow editors need two more things. A canvas may hold a second
family of edges, for example a data source hung under the step that reads it,
joined from the source's top to a named socket under the step and drawn
dashed. And an app that knows which connections are legal wants to show it
while the wire is held, refuse an illegal drop before it is reported, and
offer something on a drop on empty canvas or from a "+" beside a port.

The engine must stay domain-blind: it cannot know what either family means.

## Decision: a kind is a word on ports and edges

An edge may carry `kind` and `to_port`; a port handle may carry `data-kind`
and `data-side`. The engine uses a kind for style (repeated as `data-kind` on
the drawn path, its label and the ghost wire), for landing (a wire has the
kind of its out-port and lands only on in-ports of that kind) and nothing
else. A side sets the tangent of the curve at that end. Defaults reproduce the
old geometry exactly: an unkinded out-port leaves to the right, an unkeyed
in-end is the left middle, and an unkinded wire lands where it always did.
`to_port` and `kind` are written on the edge span only when set, so a layer
without them renders byte for byte as before.

## Decision: wire-start, before-wire, wire-end

A started wire now reports its life: `wire-start` (cancelable) once the press
passes the slop, `before-wire` (cancelable) when it lands on a node, `wire`
as before, and `wire-end` always, with a `reason` and the release point. The
stage root carries `data-pjx-graph-wiring` while a wire is held. This follows
the engine's existing `before-select` and `panel:before-close` pattern: the
`before-` event vetoes, the plain one reports.

## Decision: in-node controls opt out with `data-pjx-graph-action`

A control inside a node card is marked `data-pjx-graph-action`. Its presses
and clicks are the app's: no drag, no selection. A non-empty value fires
`pjx:graph:action {id, action, port}`, which is the hook for a "+" beside a
port.

## Alternatives considered

- **Kinds declared on the stage**, such as an `edge_kinds` prop on the stage with
  a style and port set per kind. Rejected: it duplicates what the markup
  already says, and the engine would need a schema for styles it should leave
  to CSS.
- **Inferring a port's side from where it sits on the card.** Zero markup,
  but a port near a corner flips sides with the layout. An explicit
  `data-side` is predictable.
- **Asking the app on every pointer move** (a cancelable `wire-over`). It
  makes the app's legality check run per frame and the app would still mark
  targets itself. Marking on `wire-start` and refusing on `before-wire` gives
  the same feedback with two calls.
- **A keyed in-port as the only drop target for a kinded wire.** Stricter,
  but a small socket is hard to hit; landing on the nearest matching in-port
  of the node under the pointer keeps the whole card a target.
- **Event detail in camelCase** (`toPort`). The guide posts `event.detail` as
  form values, so the detail keys match the edge dict's `to_port`.
- **A `ports` prop on `PJXGraphNode`** for top, bottom and keyed in-ports.
  Left out to keep the change small; apps with such ports write their own
  handles, as the guide shows. It can be added later without changing the
  engine.

## Consequences

- The `wire` detail gains `kind` and `to_port`. A listener reading `from`,
  `port` and `to` is unaffected; a route that receives the detail as form
  values sees two more fields.
- The instance gains `view()`, and a stage fires `pjx:graph:view` when a pan
  or zoom ends, so an app can change what it draws by scale.
- The observer also watches `data-kind` and `data-to-port` on edge spans.
- What a kind means (whether a dashed link counts as a step, which sockets
  accept which nodes) stays with the app, which must still refuse an illegal
  edge on the server.

## Related

- [ADR 0004](0004-graph-reconcile-model.md): the reconcile model these
  attributes plug into.
- [Graph guide](../guide/graph.md#edge-kinds): edge kinds, steering a wire,
  and controls inside a node.
