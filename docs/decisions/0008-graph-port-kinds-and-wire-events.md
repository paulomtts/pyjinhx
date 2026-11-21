# ADR 0008: Graph wire kinds live on ports; wires are steered by cancelable events

**Status:** Proposed, 2026-11-21. Unreleased.

## Context

The graph engine drew one family of edges: out of a right-hand out-port,
into the middle of the target's left edge, along a horizontal curve. It
reported a landed wire as `pjx:graph:wire` and nothing else, so an app could
only refuse a bad connection after the user had made it.

Apps building flow editors need two more things. A canvas may hold a second
family of edges, for example a data source hung under the step that reads it,
joined from the source's top to a named socket under the step. And an app
that knows which connections are legal wants to show it while the wire is
held, refuse an illegal drop before it is reported, and offer something on a
drop on empty canvas.

The engine must stay domain-blind: it cannot know what either family means.

## Decision: keyed in-ports and port sides

An edge may name the in-port it enters (`to_port`), and `inAnchor(id, port)`
takes the same key. A port handle may carry `data-side` (`top`, `right`,
`bottom`, `left`), which sets the tangent of the curve at that end. Defaults
reproduce the old geometry exactly: an out-port without a side leaves to the
right, an unkeyed in-end is the left middle. `to_port` is written on the edge
span only when set, so a layer without it renders byte for byte as before.

## Decision: a kind is a word on ports, used only for landing

A port handle may carry `data-kind`. A wire has the kind of the out-port it
starts from and lands only on in-ports of that kind: the one under the
pointer, else the target node's nearest one. Unkinded ports have the kind
`""`, so a canvas that sets no kind wires as before.

Edges carry no kind. Styling an edge family is already covered: every edge
has a `state`, which becomes the class `pjx-graph__edge--<state>`, and the
stage tokens (`--pjx-graph-edge-stroke`, `--pjx-graph-edge-width`, and the new
`--pjx-graph-edge-dash`) can be set on that class. Landing reads the kind
from the handles and the held wire, never from a drawn edge, and
reconciliation only needs `data-to-port` to redraw, so an edge-level kind
would have had no use once the engine stopped repeating it for CSS.

`--pjx-graph-edge-dash` (default `none`) is applied to drawn edges, matching
the existing `--pjx-graph-wire-dash` on the held wire.

## Decision: wire-start, before-wire, wire-end

A started wire now reports its life: `wire-start` (cancelable) once the press
passes the slop, `before-wire` (cancelable) when it lands on a node, `wire`
as before, and `wire-end` always, with a `reason` and the release point. The
stage root carries `data-pjx-graph-wiring="<kind>"` while a wire is held, so
an app can light the in-ports that accept it. This follows the engine's
existing `before-select` and `panel:before-close` pattern: the `before-`
event vetoes, the plain one reports.

## Alternatives considered

- **A `kind` on edges, repeated as `data-kind` on the drawn path, its label
  and the wire.** Rejected: it is a second styling channel beside `state`,
  and the state class plus tokens already express a family.
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
- **A view event and an in-node action hook.** A `pjx:graph:view` event with
  a `view()` reader, for drawing differently by scale, and a
  `data-pjx-graph-action` marker firing `pjx:graph:action`, for a "+" inside a
  node card. Left out of this change: neither is needed for keyed ports or
  wire steering, and each can be proposed on its own.
- **A `ports` prop on `PJXGraphNode`** for top, bottom and keyed in-ports.
  Left out to keep the change small; apps with such ports write their own
  handles, as the guide shows. It can be added later without changing the
  engine.

## Consequences

- The `wire` detail gains `kind` and `to_port`. A listener reading `from`,
  `port` and `to` is unaffected; a route that receives the detail as form
  values sees two more fields.
- The observer also watches `data-to-port` on edge spans.
- An edge that belongs to a family and also has a run state needs one state
  word for both (`link-failed`), since a state is a single class token.
- What a kind means (whether a link counts as a step, which sockets accept
  which nodes) stays with the app, which must still refuse an illegal edge on
  the server.

## Related

- [ADR 0004](0004-graph-reconcile-model.md): the reconcile model these
  attributes plug into.
- [Graph guide](../guide/graph.md#port-kinds-and-sides): port kinds and sides,
  and steering a wire.
