# Rebuild ADRs

Architecture decision records for the pyjinhx 1.0 rebuild. ADR 0001 predates the rebuild (canonical copy at `docs/decisions/`) and remains binding for it (PRD goal G4); it is mirrored here so the set is self-contained.

ADRs are immutable: superseded by a new ADR, never edited. New decisions made during RFCs get recorded here at decision time.

| ADR | Decision |
|---|---|
| [0001](./0001-outerhtml-only-oob-swaps.md) | outerHTML-only OOB swaps, no append/prepend modes (pre-rebuild, binding) |
| [0002](./0002-segment-list-composition.md) | Segment-list composition; children opaque by construction |
| [0003](./0003-slot-opacity.md) | Slots: opaque + truthiness only |
| [0004](./0004-drop-peer-cross-reference.md) | Peer cross-reference dropped entirely |
| [0005](./0005-post-render-tag-expansion.md) | Post-render tag expansion, one parse per level |
| [0006](./0006-strict-core-open-subclass.md) | Strict Pydantic core, open opt-in subclass |
| [0007](./0007-single-template-convention.md) | One template convention: `.pjx` + snake_case |
| [0008](./0008-drop-sfc-python-blocks.md) | SFC `{# python #}` blocks dropped |
| [0009](./0009-minimal-instance-registry.md) | Instance registry minimal, reactivity-only |
| [0010](./0010-keep-mro-resolution.md) | MRO template/asset resolution kept |
| [0011](./0011-process-decisions.md) | Process decisions (packaging, release, deferrals) |
