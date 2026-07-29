export const meta = {
  name: 'task',
  description: 'Drive one v2 subtask issue: explore, spec+plan, adversarial validation, TDD implementation, review, tests, PR. Haiku stages move the board cards. Stops at PR — never merges.',
  whenToUse: 'User asks to work a subtask card from the v2 board: "/task 251", "pick up #252", "run the task workflow on 253"',
  phases: [
    { title: 'Intake', detail: 'issue + story + rebuild docs context', model: 'sonnet' },
    { title: 'Board', detail: 'card moves (subtask + story mirror)', model: 'haiku' },
    { title: 'Spec+Plan', detail: 'spec and TDD plan' },
    { title: 'Validate', detail: 'adversarial plan review, fixes folded in' },
    { title: 'Implement', detail: 'worktree + strict TDD, granular commits', model: 'sonnet' },
    { title: 'Review', detail: 'branch diff review + fixes' },
    { title: 'Tests', detail: 'full suite + basedpyright + CI-version ruff + integrity gate', model: 'sonnet' },
    { title: 'PR', detail: 'push + open PR (no merge)', model: 'sonnet' },
  ],
}

// ── args ─────────────────────────────────────────────────────────────────────
let raw = args
if (typeof raw === 'string') {
  try { raw = JSON.parse(raw) } catch { raw = Number(raw) }
}
const issue = Number(raw && raw.issue !== undefined ? raw.issue : raw)
if (!Number.isInteger(issue) || issue <= 0) throw new Error('task workflow needs an issue number, e.g. args: {"issue": 251}')

const REPO_DIR = '/home/mtts/Code/libs/pyjinhx'
const WORKTREE = `${REPO_DIR}/.claude/worktrees/task-${issue}`
const BRANCH = `task-${issue}`

// ── board (Project 12) — Haiku stages, sole board writers ────────────────────
const OPTION_IDS = { backlog: 'a4448373', spec: '07356194', ready: '5d5646cc', implementing: '20e71636', 'in-review': '6554ad50', testing: 'f397e470', done: 'ce6ea6d1' }
const OPTION_NAMES = { backlog: 'Backlog', spec: 'Spec', ready: 'Ready', implementing: 'In progress', 'in-review': 'In review', testing: 'Testing', done: 'Done' }

function board(stage) {
  return agent(`Move the Project 12 card for pyjinhx issue #${issue} to Status "${OPTION_NAMES[stage]}", then mirror its parent story. Use ONLY the Status-setting mutations below — never create, close, edit, or delete anything.

Run these bash commands exactly (note: pass the option id with -f, NOT -F — -F coerces numeric-looking strings to int and the mutation rejects it):

1. Find the card:
ITEM_ID=$(gh api graphql -f query='query($n:Int!){repository(owner:"paulomtts",name:"pyjinhx"){issue(number:$n){projectItems(first:10){nodes{id project{id}}}}}}' -F n=${issue} --jq '.data.repository.issue.projectItems.nodes[] | select(.project.id=="PVT_kwHOBZmM8c4BewiO") | .id')

2. Set its Status:
gh api graphql -f query='mutation($i:ID!,$o:String!){updateProjectV2ItemFieldValue(input:{projectId:"PVT_kwHOBZmM8c4BewiO",itemId:$i,fieldId:"PVTSSF_lAHOBZmM8c4BewiOzhZIXw8",value:{singleSelectOptionId:$o}}){projectV2Item{id}}}' -f i="$ITEM_ID" -f o="${OPTION_IDS[stage]}"

3. Mirror the parent story to the least-advanced of its sub-issues. Fetch:
gh api graphql -f query='query($n:Int!){repository(owner:"paulomtts",name:"pyjinhx"){issue(number:$n){parent{number subIssues(first:50){nodes{projectItems(first:10){nodes{project{id} fieldValueByName(name:"Status"){... on ProjectV2ItemFieldSingleSelectValue{name}}}}}}}}}}' -F n=${issue}
If there is no parent, stop here. Otherwise, among the sub-issues' Status names on project PVT_kwHOBZmM8c4BewiO (missing value counts as "Backlog"), find the MINIMUM by this order: Backlog < Spec < Ready < In progress < In review < Testing < Done. Then find the parent's card with the step-1 query (its issue number) and set its Status with the step-2 mutation using this option-id map: Backlog=a4448373 Spec=07356194 Ready=5d5646cc "In progress"=20e71636 "In review"=6554ad50 Testing=f397e470 Done=ce6ea6d1.

Return one line: "#${issue} -> ${OPTION_NAMES[stage]}; story #<P> -> <Name>" (or "no parent" / the exact error).`,
    { label: `board:${stage}`, phase: 'Board', model: 'haiku', effort: 'low' })
}

// ── 1. intake ────────────────────────────────────────────────────────────────
phase('Intake')
const intake = await agent(`Intake for pyjinhx v2 subtask #${issue} in ${REPO_DIR}.

1. \`gh issue view ${issue} --json title,body,labels,milestone\` — if the labels do NOT include "subtask" (e.g. it is a story), set refused=true with the reason and stop.
2. Read the parent story (\`gh api graphql\` on issue.parent or the "Subtask of #N" line in the body) and list its sibling sub-issues with states.
3. Read docs/superpowers/rebuild/architecture-overview.md, docs/superpowers/rebuild/implementation-overview.md, and any ADRs the story or subtask cites (docs/superpowers/rebuild/adr/).
4. Locate the code the subtask touches: existing pyjinhx2/ modules, sibling tests, relevant v0.x reference code (pyjinhx/).

Return: what #${issue} must deliver, exact constraints from the docs (invariants, types, conventions the subtask must obey), relevant file:line references, and what sibling subtasks own (so this one doesn't drift into them).`,
  { label: `intake:#${issue}`, phase: 'Intake', model: 'sonnet', schema: {
    type: 'object', required: ['refused', 'summary'],
    properties: { refused: { type: 'boolean' }, reason: { type: 'string' }, summary: { type: 'string' } },
  } })
if (!intake || intake.refused) return { issue, refused: true, reason: intake ? intake.reason : 'intake agent died' }

await board('spec')

// ── 2. spec + plan (Fable) ───────────────────────────────────────────────────
phase('Spec+Plan')
const planPath = await agent(`Write the spec + TDD implementation plan for pyjinhx v2 subtask #${issue} in ${REPO_DIR}.

Intake findings:
${intake.summary}

Rules:
- Spec first (scope, observable behavior, error paths, test list — half a page for most subtasks), then the plan in the superpowers:writing-plans format: bite-sized tasks, each step one action with real code blocks, RED before GREEN, no placeholders.
- Scale to subtask size. One subtask = usually one module/function + its tests.
- Branch will be ${BRANCH}, worktree ${WORKTREE}. Full suite is \`uv run pytest tests/\`; typecheck \`uvx basedpyright\` (standard mode); lint gate is ruff 0.16.0 (CI pins it — check locally with \`uvx ruff@0.16.0\`).
- Save to docs/superpowers/plans/$(date +%Y-%m-%d)-issue-${issue}.md (compute the date with bash). No hard-wrapped prose.

Return ONLY the absolute path of the saved plan file.`,
  { label: `plan:#${issue}`, phase: 'Spec+Plan', model: 'fable' })
if (!planPath) throw new Error('spec+plan agent died')
const plan = planPath.trim()

// ── 3. adversarial validation (Fable) ────────────────────────────────────────
phase('Validate')
const verdict = await agent(`Adversarial review (kind:spec) of ${plan} — spec+plan for pyjinhx v2 subtask #${issue} in ${REPO_DIR}.

Try to BREAK it before implementation: contradictions with docs/superpowers/rebuild/ (architecture-overview invariants, implementation-overview, ADRs), decisions that bite sibling subtasks, dishonest or tautological tests, config side-effects, steps not executable verbatim. Verify every suspicion against the actual files/tools before reporting (run commands if needed).

Fold every CONFIRMED fix directly into the plan file (edit it), keeping its structure. Return blockers=true only if something unresolvable remains (spec contradiction needing a human decision) with the reason.`,
  { label: `validate:#${issue}`, phase: 'Validate', model: 'fable', schema: {
    type: 'object', required: ['blockers', 'summary'],
    properties: { blockers: { type: 'boolean' }, reason: { type: 'string' }, summary: { type: 'string' } },
  } })
if (!verdict || verdict.blockers) {
  await agent(`Comment on pyjinhx issue #${issue}: the /task workflow stopped at validation. Reason: ${verdict ? verdict.reason : 'validator died'}. Use \`gh issue comment ${issue} --body "..."\` with a concise version.`, { label: 'blocked-comment', phase: 'Validate', model: 'haiku', effort: 'low' })
  return { issue, blocked: 'validation', reason: verdict ? verdict.reason : 'validator died' }
}

await board('ready')
await board('implementing')

// ── 4. implement (Sonnet, TDD) ───────────────────────────────────────────────
phase('Implement')
const impl = await agent(`Implement pyjinhx v2 subtask #${issue} from the validated plan at ${plan}.

Setup: from ${REPO_DIR}, run \`git fetch origin && git worktree add ${WORKTREE} -b ${BRANCH} origin/master\` (if the worktree exists, reuse it). Work ONLY inside ${WORKTREE}. Run \`uv sync\` there, then a baseline \`uv run pytest tests/ -q\` — report if baseline is red and stop.

Then STRICT TDD per the plan: write the failing test, RUN it and confirm it fails for the right reason, minimal code to green, re-run, refactor, commit granularly (conventional commits, reference #${issue}). Never write production code without having watched its test fail. Mutation-check any meta/guard tests (make them fail once on purpose). End every commit message with:
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Do NOT push, do NOT open a PR. Return: commits made (oneline), test count added, deviations from the plan with reasons.`,
  { label: `implement:#${issue}`, phase: 'Implement', model: 'sonnet' })
if (!impl) throw new Error('implement agent died')

// ── 5. review (Fable) + fixes (Sonnet) ───────────────────────────────────────
phase('Review')
const review = await agent(`Review the branch diff in ${WORKTREE}: \`git diff origin/master...HEAD\`. Context: pyjinhx v2 subtask #${issue}; plan at ${plan}; rebuild constraints in docs/superpowers/rebuild/ (import-purity of segments.py, hard invariants, ADRs). Implementer's report:
${impl}

One line per finding, severity-tagged (blocker/major/minor), no praise, no scope creep. Verify each finding against the actual code before reporting. Return findings=[] if clean.`,
  { label: `review:#${issue}`, phase: 'Review', model: 'fable', schema: {
    type: 'object', required: ['findings'],
    properties: { findings: { type: 'array', items: { type: 'string' } } },
  } })
if (review && review.findings.length > 0) {
  await agent(`In ${WORKTREE}, fix these review findings on branch ${BRANCH} (TDD where behavior changes: failing test first), commit granularly, end commits with the Co-Authored-By line for Claude Fable 5 <noreply@anthropic.com>:
${review.findings.join('\n')}

Skip any finding that is wrong — say why instead. Return what was fixed vs skipped.`,
    { label: `fix:#${issue}`, phase: 'Review', model: 'sonnet' })
}

// ── 6. tests ─────────────────────────────────────────────────────────────────
phase('Tests')
const tests = await agent(`Full verification in ${WORKTREE} (branch ${BRANCH}):

1. \`uv run pytest tests/ -q\` — full suite.
2. \`uvx basedpyright pyjinhx2/ tests/pyjinhx2/\` — 0 errors required.
3. \`uvx ruff@0.16.0 check .\` and \`uvx ruff@0.16.0 format --check .\` (CI pins 0.16.0). Auto-fix + commit if needed.
4. Test-integrity gate on \`git diff origin/master...HEAD -- tests/\`: no weakened/deleted assertions, no tautologies, no tests that merely mirror the implementation, every new behavior has a test that would fail without its code. Report violations honestly — fix them, don't argue.

Return passed=true only if ALL of 1-4 are green after your fixes (commit any fixes).`,
  { label: `verify:#${issue}`, phase: 'Tests', model: 'sonnet', schema: {
    type: 'object', required: ['passed', 'detail'],
    properties: { passed: { type: 'boolean' }, detail: { type: 'string' } },
  } })
if (!tests || !tests.passed) return { issue, blocked: 'tests', detail: tests ? tests.detail : 'verify agent died' }

// ── 7. PR — no merge ─────────────────────────────────────────────────────────
phase('PR')
const pr = await agent(`From ${WORKTREE}: push branch ${BRANCH} (\`git push -u origin ${BRANCH}\`) and open a PR with \`gh pr create\` — title from the branch's main commit, body summarizing the change (what + why, test count), containing the line "Closes #${issue}", ending with:
🤖 Generated with [Claude Code](https://claude.com/claude-code)

Do NOT merge. Do NOT enable auto-merge. Return ONLY the PR URL.`,
  { label: `pr:#${issue}`, phase: 'PR', model: 'sonnet' })
if (!pr) throw new Error('pr agent died')

await board('in-review')

return { issue, pr: pr.trim(), plan, tests: tests.detail }
