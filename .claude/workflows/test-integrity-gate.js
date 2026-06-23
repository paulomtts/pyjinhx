export const meta = {
  name: 'test-integrity-gate',
  description: 'Adversarial judge for test-suite integrity. Given the branch test diff vs the merge-base, one guilty-by-default skeptic per flagged test (modified, deleted, or new) decides whether the change is legitimate (spec/plan-justified or behavior-preserving) or gaming (a weakened/deleted existing test, or a hollow new test).',
  whenToUse: 'Invoked by the /feature command after implementation. The command computes the test diff vs merge-base and passes the flagged items; this workflow returns a per-item verdict. The remediation loop lives in the command, not here.',
  phases: [
    { title: 'Judge', detail: 'one adversarial, guilty-by-default skeptic per flagged test item renders a legitimacy verdict' },
  ],
}

const ARGS = typeof args === 'string' ? JSON.parse(args || '{}') : (args || {})

if (ARGS.selfTest) {
  log('test-integrity-gate: self-test OK')
  return { ok: true, name: 'test-integrity-gate' }
}

const SPEC = ARGS.specPath
const PLAN = ARGS.planPath
const ITEMS = ARGS.items || []
if (!SPEC) throw new Error('test-integrity-gate: args.specPath is required')
if (!ITEMS.length) {
  log('test-integrity-gate: no flagged test items — PASS')
  return { items: [], violations: [] }
}

const ASKS = {
  modified: 'This EXISTING test was MODIFIED. Assume it was WEAKENED or retargeted to make failing code pass, until proven otherwise. Legitimate ONLY if (a) the spec or plan documents a behavior change that requires this assertion to change, OR (b) it is a provably behavior-preserving refactor (rename, fixture move, dedup) that does NOT relax what is asserted. ALSO: if the diff adds new test functions, check those are not hollow.',
  deleted: 'This EXISTING test was DELETED. Assume an inconvenient test was removed to go green, until proven otherwise. Legitimate ONLY if the spec or plan removed or changed the behavior it covered.',
  new: 'This is a NEW test. Assume it is HOLLOW (asserts trivia, is so mocked-out that nothing real runs, or never drives the code path it claims) until proven otherwise. Legitimate ONLY if it genuinely exercises real behavior with meaningful assertions.',
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    legitimate: { type: 'boolean', description: 'false on ANY genuine doubt (guilty-by-default).' },
    reason: { type: 'string', description: 'Cite the spec/plan section (or its absence) and what the test actually asserts.' },
  },
  required: ['legitimate', 'reason'],
}

phase('Judge')

const verdicts = (await parallel(
  ITEMS.map((it) => () =>
    agent(`You are an adversarial test-integrity judge. Be GUILTY-BY-DEFAULT: your job is to REFUTE the legitimacy of this test change.

SPEC: ${SPEC}
${PLAN ? `PLAN: ${PLAN}` : ''}
You may read the spec, the plan, the test file, and the source under test.

FLAGGED ${it.category.toUpperCase()} TEST — ${it.path} (id ${it.id}):
${ASKS[it.category] || ASKS.modified}

DIFF / CONTENT:
<<<DIFF
${it.diff || '(read the file at the path above)'}
DIFF>>>

Read the spec/plan and the relevant source, then decide legitimate true/false. On ANY genuine doubt, return legitimate=false. Give a concrete reason citing the spec/plan section (or its absence) and what the test actually asserts.`,
      { label: `judge:${it.id}`, phase: 'Judge', schema: VERDICT_SCHEMA },
    ).then((v) => ({ id: it.id, path: it.path, category: it.category, ...v })),
  ),
)).filter(Boolean)

const violations = verdicts.filter((v) => !v.legitimate)
log(`Judge: ${violations.length}/${verdicts.length} flagged test changes failed the integrity check.`)

return { items: verdicts, violations }
