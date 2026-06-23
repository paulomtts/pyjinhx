export const meta = {
  name: 'architecture-report-audit',
  description: 'Generate a source-grounded pyjinhx architecture report (architecture-map.md layout), adversarially verify every claim against the code, then synthesize the verified final report into docs/superpowers/reports/',
  whenToUse: 'When you want a fresh architecture/duplication map of the pyjinhx core engine that mirrors docs/superpowers/architecture-map.md and is adversarially fact-checked before being written.',
  phases: [
    { title: 'Map', detail: 'four parallel readers gather ground-truth facts (with file:line citations) from disjoint slices of the core engine' },
    { title: 'Draft', detail: 'one writer assembles the facts into a report following the architecture-map.md layout + emits a list of falsifiable claims' },
    { title: 'Verify', detail: 'one adversarial skeptic per claim re-reads the source and tries to refute it' },
    { title: 'Synthesize', detail: 'one writer applies the verdicts, drops/fixes refuted claims, and writes the final report to disk' },
    { title: 'Critique', detail: 'one critic checks layout fidelity against architecture-map.md and spot-checks surviving claims' },
  ],
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const LAYOUT = 'docs/superpowers/architecture-map.md'
const TARGET = 'docs/superpowers/reports/architecture-report.md'

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------
const MAP_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    subsystem: { type: 'string' },
    facts: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          statement: { type: 'string', description: 'A precise, falsifiable structural fact.' },
          evidence: { type: 'string', description: 'file:line citation(s) proving it, e.g. reactive.py:120.' },
        },
        required: ['statement', 'evidence'],
      },
    },
    diagram: { type: 'string', description: 'A small ASCII/box diagram fragment for this subsystem, in the style of architecture-map.md.' },
    reuse: { type: 'string', description: 'Which shared modules (registry, render-session, cache, utils, etc.) this subsystem reads/uses.' },
  },
  required: ['subsystem', 'facts', 'diagram', 'reuse'],
}

const DRAFT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    markdown: { type: 'string', description: 'The full report markdown, mirroring architecture-map.md section structure.' },
    claims: {
      type: 'array',
      description: 'Every falsifiable claim in the report that asserts something about the code (class relationships, line numbers, duplication, single-path, etc.).',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          id: { type: 'string' },
          text: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
        },
        required: ['id', 'text', 'files'],
      },
    },
  },
  required: ['markdown', 'claims'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    id: { type: 'string' },
    status: { type: 'string', enum: ['confirmed', 'refuted', 'imprecise'] },
    evidence: { type: 'string', description: 'file:line evidence found while attempting to refute.' },
    correction: { type: 'string', description: 'If refuted/imprecise, the corrected statement; else empty.' },
  },
  required: ['id', 'status', 'evidence', 'correction'],
}

const SYNTH_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    path: { type: 'string' },
    claims_total: { type: 'number' },
    claims_confirmed: { type: 'number' },
    claims_refuted: { type: 'number' },
    claims_imprecise: { type: 'number' },
    corrections: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['path', 'summary', 'corrections'],
}

const CRITIC_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    layout_match: { type: 'boolean' },
    diagram_ok: { type: 'boolean' },
    missing_sections: { type: 'array', items: { type: 'string' } },
    issues: { type: 'array', items: { type: 'string' } },
    spotchecks: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          claim: { type: 'string' },
          holds: { type: 'boolean' },
          note: { type: 'string' },
        },
        required: ['claim', 'holds', 'note'],
      },
    },
    verdict: { type: 'string' },
  },
  required: ['layout_match', 'diagram_ok', 'verdict'],
}

// ---------------------------------------------------------------------------
// Phase 1 — Map: four parallel readers over disjoint slices of the engine.
// They read SOURCE ONLY (never architecture-map.md) so the report is
// independently regenerated, not copied.
// ---------------------------------------------------------------------------
phase('Map')

const COMMON = `You are mapping the pyjinhx core engine (a Python server-rendered-component + htmx library) to produce ground-truth facts for an architecture report.

RULES:
- Read the ACTUAL source files. Do NOT read docs/superpowers/architecture-map.md or any docs/ file — regenerate facts from code only.
- Every fact MUST carry a file:line citation you actually verified (open the file, find the line). No guessing.
- Prefer precise, falsifiable statements ("ReactiveComponent subclasses BaseComponent at reactive.py:NN") over vague ones.
- Note any code duplication, double-work, or tight/implicit coupling you observe, with evidence.`

const MAPPERS = [
  {
    label: 'map:layers',
    subsystem: 'layer-stack',
    prompt: `${COMMON}

YOUR SLICE — the layer stack & type hierarchy. Read: pyjinhx/__init__.py, pyjinhx/base.py, pyjinhx/reactive.py, pyjinhx/config.py, pyjinhx/integrations/fastapi.py, pyjinhx/integrations/redis.py, pyjinhx/integrations/sqlite.py.

Establish, with citations:
- The exact class relationship between ReactiveComponent and BaseComponent (subclass? composition? where defined).
- What config.setup() does as a composition root (scope, backend selection).
- What integrations/fastapi.py wires (middleware, lifespan) and whether it just delegates to request_scope.
- The pluggable invalidation backends (redis/sqlite) and the interface they implement.
- Build an ASCII layer-stack diagram (app edge → composition root → reactive overlay → render core → renderer → mechanics → shared spine → pluggable backends).`,
  },
  {
    label: 'map:static-render',
    subsystem: 'static-render-roundtrip',
    prompt: `${COMMON}

YOUR SLICE — the static render round-trip. Read: pyjinhx/base.py, pyjinhx/renderer.py, pyjinhx/finder.py, pyjinhx/tags.py, pyjinhx/root_attrs.py, pyjinhx/assets.py, pyjinhx/utils.py.

Trace, with line citations, the path from Cls().render() through _render() through the Renderer: context build, cycle guard, nested-component wrapping, template lookup (Finder), Jinja render, custom <PascalCase> tag expansion + recursion, reactive-markup stamping, root-attr application, and asset injection.

CRITICAL: examine the attribute-stamping / root-attr steps closely. Is the root opening tag located and re-parsed MORE THAN ONCE per render (e.g. stamp_reactive_markup / utils.stamp_root_attributes vs root_attrs.apply_root_attrs / find_single_root)? Cite exact lines and function names. State plainly whether this is genuine duplicated work.
Build an ASCII flow diagram of the round-trip.`,
  },
  {
    label: 'map:reactive-oob',
    subsystem: 'reactive-overlay-oob-cache',
    prompt: `${COMMON}

YOUR SLICE — the reactive overlay, OOB swap, load-cache, and mutations. Read: pyjinhx/reactive.py, pyjinhx/cache.py, pyjinhx/mutations.py, pyjinhx/keys.py, pyjinhx/client.py.

Establish, with citations:
- How ReactiveComponent.render() differs from / reuses BaseComponent._render() (does OOB re-use _render or a bespoke renderer?).
- Where the cache boundary is: does __init_subclass__ wrap the user's load() into a cached wrapper, and do BOTH primary render and OOB regions go through that same cache? (one caching path or two?)
- The OOB swap flow (MountedManifest parse, per-region fresh load()+_render, hash compare, hx-swap-oob).
- How @mutates invalidates the cache (reverse index / coerce keys).
- The manifest parsers in client.py (LoadedAssets, MountedManifest, TriggerManifest) — same shape or distinct schemas? Is this duplication?
- Build an ASCII diagram of the reactive request → OOB response.`,
  },
  {
    label: 'map:spine',
    subsystem: 'request-scope-spine',
    prompt: `${COMMON}

YOUR SLICE — the request-scope spine and shared machinery. Read: pyjinhx/registry.py, pyjinhx/context.py, pyjinhx/client.py, pyjinhx/utils.py, pyjinhx/keys.py, pyjinhx/cache.py, pyjinhx/mutations.py.

Establish, with citations:
- Registry.request_scope(): is it ONE context manager that initializes & tears down every cross-cutting concern (MutationTracker, LoadCache, instance registry, runtime-injected flag, PjxContext, ClientBackend)? List what it opens, in order, with lines.
- Are these accessed via ContextVars rather than passed as parameters? (cite ContextVar definitions). What happens to a render that runs OUTSIDE request_scope() — does it silently get defaults?
- Build the shared-machinery REUSE MATRIX data: for each of {Registry, RenderSession, LoadCache, MutationTracker, PjxContext, ClientBackend, keys.coerce_*, utils} list which of {base, renderer, reactive, assets, cache, tags, client} import/use it. Cite where the import/use happens.
- Build an ASCII diagram of request_scope() opening all state.`,
  },
]

const maps = (await parallel(
  MAPPERS.map((m) => () => agent(m.prompt, { label: m.label, phase: 'Map', schema: MAP_SCHEMA })),
)).filter(Boolean)

log(`Map phase complete: ${maps.length}/${MAPPERS.length} subsystems mapped, ${maps.reduce((n, m) => n + (m.facts ? m.facts.length : 0), 0)} cited facts gathered.`)

// ---------------------------------------------------------------------------
// Phase 2 — Draft: assemble the facts into a report mirroring the layout.
// ---------------------------------------------------------------------------
phase('Draft')

const draft = await agent(
  `You are the report writer. Produce an architecture report for the pyjinhx core engine.

LAYOUT: Read ${LAYOUT} and mirror its SECTION STRUCTURE and diagram style EXACTLY — same sections in the same order:
  1. Title + intro paragraph (state module count and approximate total LOC of the core engine — EXCLUDE the builtins/ui component library from "core engine" LOC; count it separately if you mention it).
  2. "## 1. The layer stack — what sits on what" + ASCII diagram + the key structural fact.
  3. "## 2. The static render round-trip" + ASCII flow diagram.
  4. "## 3. The reactive overlay + OOB swap" + ASCII diagram + "things to notice".
  5. "## 4. The request-scope spine" + ASCII diagram + analysis.
  6. "## 5. Shared-machinery matrix" + ASCII matrix.
  7. "## Duplication & efficiency assessment" with subsections: "### Confirmed — worth fixing", "### Confirmed — acceptable, not worth touching", "### Efficiency observations (integration, not duplication)", "### Net".

DO NOT copy architecture-map.md's prose or claims. Use it ONLY for structure/style. Every claim, number, line citation, and diagram MUST be derived from the FACTS below.

FACTS (from four source-reading agents):
${JSON.stringify(maps, null, 2)}

Write the report into "markdown". Then enumerate in "claims" EVERY falsifiable assertion the report makes about the code — especially: the ReactiveComponent/BaseComponent relationship, single-render-path claims, the cache-boundary claim, the double-attribute-splice duplication claim, the ContextVar-coupling claim, every file:line citation, and every entry asserted in the reuse matrix. Each claim needs an id (c1, c2, ...), its text, and the files a verifier should open. Be exhaustive — aim for 12-20 claims; do not leave a load-bearing assertion unlisted.`,
  { phase: 'Draft', schema: DRAFT_SCHEMA },
)

log(`Draft complete: ${draft.markdown.length} chars, ${draft.claims.length} falsifiable claims to verify.`)

// ---------------------------------------------------------------------------
// Phase 3 — Verify: one adversarial skeptic per claim, re-reading source.
// ---------------------------------------------------------------------------
phase('Verify')

const verdicts = (await parallel(
  draft.claims.map((c) => () =>
    agent(
      `You are an ADVERSARIAL fact-checker. Your job is to REFUTE the following claim about the pyjinhx codebase by reading the actual source. Assume it is wrong until the code proves it right.

CLAIM ${c.id}: ${c.text}
Files to open: ${(c.files || []).join(', ') || '(infer from the claim)'}

Open the cited files, find the exact lines, and check:
- Are the line numbers / function names / class names accurate?
- Is the structural assertion (subclass, single-path, one cache boundary, duplicated splice, ContextVar access, reuse-matrix cell) literally true in the current code?
- For duplication claims: is it REALLY duplicated work, or reuse / two distinct schemas / two phases of one job?

Return status:
- "confirmed" only if the code unambiguously supports the claim (cite the proving line in evidence).
- "imprecise" if the gist is right but a number/name/detail is off (give the corrected statement in correction).
- "refuted" if it is false or unsupported (explain in evidence, give the truth in correction).
When uncertain, prefer "imprecise" or "refuted" over "confirmed". Always fill correction (empty string only if confirmed).`,
      { label: `verify:${c.id}`, phase: 'Verify', schema: VERDICT_SCHEMA },
    ),
  ),
)).filter(Boolean)

const confirmed = verdicts.filter((v) => v.status === 'confirmed').length
const imprecise = verdicts.filter((v) => v.status === 'imprecise').length
const refuted = verdicts.filter((v) => v.status === 'refuted').length
log(`Verify complete: ${confirmed} confirmed, ${imprecise} imprecise, ${refuted} refuted (of ${verdicts.length}).`)

// ---------------------------------------------------------------------------
// Phase 4 — Synthesize: apply verdicts, write the final report to disk.
// ---------------------------------------------------------------------------
phase('Synthesize')

const synth = await agent(
  `You are the final editor. Produce the verified architecture report and WRITE it to disk.

DRAFT MARKDOWN:
<<<DRAFT
${draft.markdown}
DRAFT>>>

ADVERSARIAL VERDICTS (apply every one):
${JSON.stringify(verdicts, null, 2)}

INSTRUCTIONS:
- For each "confirmed" claim: keep as-is.
- For each "imprecise" claim: replace the wording with the verdict's correction (fix the number/name/line).
- For each "refuted" claim: remove the false assertion, OR replace it with the correction if the verdict supplies a true replacement. Never leave a refuted claim in the report.
- Keep the architecture-map.md layout (all 7 sections, ASCII diagrams intact and correctly aligned).
- Preserve the "Each claim below was verified against the source." spirit — the assessment section must reflect what actually survived verification.
- Do a final read for internal consistency (diagrams must match the prose; line numbers must match what verification confirmed).

Then WRITE the finished markdown to the file path "${TARGET}" using the Write tool (create parent dirs if needed). Return the path you wrote, the counts, the list of concrete corrections you applied, and a 2-3 sentence summary of the report's verdict on duplication/integration.`,
  { phase: 'Synthesize', schema: SYNTH_SCHEMA },
)

log(`Synthesized + wrote ${synth.path} (${synth.corrections ? synth.corrections.length : 0} corrections applied).`)

// ---------------------------------------------------------------------------
// Phase 5 — Critique: independent layout + spot-check of the written file.
// ---------------------------------------------------------------------------
phase('Critique')

const critic = await agent(
  `You are an independent reviewer. Read TWO files:
  1. The reference layout: ${LAYOUT}
  2. The freshly written report: ${TARGET}

Check:
- layout_match: does the new report mirror the reference's section structure (intro + 5 numbered sections + "Duplication & efficiency assessment" with its 4 subsections)? List any missing_sections.
- diagram_ok: are the ASCII diagrams present, well-formed, and aligned (box borders line up)?
- Spot-check 3 of the report's load-bearing claims by opening the cited source files yourself (e.g. the ReactiveComponent/BaseComponent subclass relation, the cache-boundary claim, and the headline duplication claim). For each, report holds=true/false with a note.
- issues: anything wrong, internally inconsistent, or copied verbatim from the reference.
- verdict: PASS or FAIL with one sentence.`,
  { phase: 'Critique', schema: CRITIC_SCHEMA },
)

log(`Critique: ${critic.verdict}`)

return {
  target: synth.path,
  draft_claims: draft.claims.length,
  verification: { confirmed, imprecise, refuted },
  corrections: synth.corrections,
  summary: synth.summary,
  critic,
}
