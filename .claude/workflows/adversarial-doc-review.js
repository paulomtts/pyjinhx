export const meta = {
  name: 'adversarial-doc-review',
  description: 'Adversarially red-team a feature spec or implementation plan: parallel critics raise falsifiable critiques across fixed dimensions, one skeptic per critique tries to refute it, and survivors are synthesized into an actionable findings list.',
  whenToUse: 'Invoked by the /feature command after brainstorming (kind:spec) and after writing-plans (kind:plan) to stress-test the document before it is acted on.',
  phases: [
    { title: 'Critique', detail: 'one critic per review dimension raises falsifiable critiques of the document' },
    { title: 'Verify', detail: 'one adversarial skeptic per critique tries to refute it; plausible-but-wrong nits die here' },
    { title: 'Synthesize', detail: 'one editor consolidates surviving critiques into a deduped findings list' },
  ],
}

const ARGS = typeof args === 'string' ? JSON.parse(args || '{}') : (args || {})

if (ARGS.selfTest) {
  log('adversarial-doc-review: self-test OK')
  return { ok: true, name: 'adversarial-doc-review' }
}

const KIND = ARGS.kind || 'spec'
const DOC = ARGS.docPath
const SPEC = ARGS.specPath || DOC
if (!DOC) throw new Error('adversarial-doc-review: args.docPath is required')

const DIMENSIONS = {
  spec: [
    { key: 'ambiguity', title: 'Ambiguity', prompt: 'Find requirements with two valid readings. Quote each and state the divergent interpretations.' },
    { key: 'edge-cases', title: 'Missing edge cases', prompt: 'Find failure modes, boundary conditions, or states the spec never addresses.' },
    { key: 'testability', title: 'Testability', prompt: 'Find requirements that are untestable or unfalsifiable as written — no observable pass/fail.' },
    { key: 'scope', title: 'Scope', prompt: 'Find scope creep (anything beyond the stated goal) AND any stated goal left unaddressed.' },
    { key: 'contradiction', title: 'Internal contradiction', prompt: 'Find statements or sections that conflict with each other or with the architecture.' },
    { key: 'assumptions', title: 'Unstated assumptions', prompt: 'Surface assumptions the design silently depends on but never states.' },
  ],
  plan: [
    { key: 'fidelity', title: 'Spec fidelity', prompt: 'For each task, check it implements a real spec requirement; flag tasks that drift from or contradict the spec, and spec requirements with no task.' },
    { key: 'verifiability', title: 'Verifiability', prompt: "Flag steps whose verification is missing, vague, or wouldn't actually prove the step works." },
    { key: 'tdd', title: 'TDD ordering', prompt: 'Flag tasks that write implementation before a failing test, or that lack a real test cycle (where a test harness exists).' },
    { key: 'sizing', title: 'Task sizing', prompt: 'Flag oversized tasks (multiple independent deliverables) and missing tasks.' },
    { key: 'coupling', title: 'Hidden coupling', prompt: "Flag 'independent' tasks that secretly depend on each other's internals or ordering." },
  ],
}[KIND]
if (!DIMENSIONS) throw new Error(`adversarial-doc-review: unknown kind "${KIND}"`)

const CRITIQUE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    dimension: { type: 'string' },
    critiques: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          problem: { type: 'string', description: 'The concrete, falsifiable problem.' },
          where: { type: 'string', description: 'Section / quote / task pinpointing the location in the document.' },
          severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
        },
        required: ['problem', 'where', 'severity'],
      },
    },
  },
  required: ['dimension', 'critiques'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    survives: { type: 'boolean', description: 'true ONLY if the problem is real and worth fixing.' },
    reason: { type: 'string' },
  },
  required: ['survives', 'reason'],
}

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
          where: { type: 'string' },
          problem: { type: 'string' },
          suggestion: { type: 'string' },
        },
        required: ['severity', 'where', 'problem', 'suggestion'],
      },
    },
  },
  required: ['findings'],
}

phase('Critique')

const COMMON = `You are adversarially reviewing a ${KIND === 'spec' ? 'feature specification' : 'implementation plan'} BEFORE any code is written. Read the document at ${DOC}.${KIND === 'plan' ? ` It must faithfully implement the spec at ${SPEC} — read that too.` : ''}
Raise only FALSIFIABLE, specific critiques (a skeptic could check each and confirm or refute it). No vague "could be clearer". For each: the precise location/quote, the concrete problem, and a severity (blocker|major|minor). Return an empty critiques array if your lens finds nothing real.`

const critiqueBatches = (await parallel(
  DIMENSIONS.map((d) => () =>
    agent(`${COMMON}\n\nYOUR LENS — ${d.title}: ${d.prompt}\nReport "dimension": "${d.key}".`,
      { label: `critique:${d.key}`, phase: 'Critique', schema: CRITIQUE_SCHEMA }),
  ),
)).filter(Boolean)

const critiques = []
critiqueBatches.forEach((b) =>
  (b.critiques || []).forEach((c, i) => critiques.push({ id: `${b.dimension}-${i + 1}`, ...c })),
)
log(`Critique: ${critiques.length} critiques raised across ${critiqueBatches.length} lenses.`)

phase('Verify')

const verdicts = (await parallel(
  critiques.map((c) => () =>
    agent(`You are an adversarial skeptic. Try to REFUTE this critique of the ${KIND} — assume it is wrong or a non-issue until the document proves otherwise. Read ${DOC}${KIND === 'plan' ? ` and the spec ${SPEC}` : ''}.

CRITIQUE ${c.id} [${c.severity}] @ ${c.where}:
${c.problem}

Return survives=true ONLY if the problem is real, present in the document, and worth fixing. Return survives=false if it is a non-issue, already handled elsewhere in the document, or out of scope. Give your reason.`,
      { label: `verify:${c.id}`, phase: 'Verify', schema: VERDICT_SCHEMA },
    ).then((v) => ({ ...c, ...v })),
  ),
)).filter(Boolean)

const survivors = verdicts.filter((v) => v.survives)
log(`Verify: ${survivors.length}/${verdicts.length} critiques survived refutation.`)

phase('Synthesize')

if (!survivors.length) {
  log('Synthesize: no surviving findings — document passes adversarial review.')
  return { kind: KIND, doc: DOC, findingsCount: 0, findings: [] }
}

const synth = await agent(
  `You are the editor. Below are adversarially-verified critiques of the ${KIND} at ${DOC} that survived refutation:
${JSON.stringify(survivors.map(({ id, severity, where, problem }) => ({ id, severity, where, problem })), null, 2)}

Dedup overlapping critiques and turn each into an actionable finding: { severity, where, problem, suggestion }. Order blocker → major → minor. Do NOT invent new problems; only consolidate what is listed.`,
  { phase: 'Synthesize', schema: FINDINGS_SCHEMA },
)

log(`Synthesize: ${synth.findings.length} findings.`)

return { kind: KIND, doc: DOC, findingsCount: synth.findings.length, findings: synth.findings }
