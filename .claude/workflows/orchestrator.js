export const meta = {
  name: 'orchestrator',
  description: 'Drive a whole milestone: compute the story dependency DAG, dispatch each level\'s stories in parallel via the task workflow (orchestrated mode), serialize their merges through one lock, resolve conflicts with a capped Opus agent, and full-stop on escalation.',
  whenToUse: 'User asks to run a whole milestone: "/orchestrator 7 l2-registry-assets", "run milestone 7 end-to-end"',
  phases: [
    { title: 'Detect', detail: 'stories, DAG edges, remaining subtasks by title ordinal', model: 'haiku' },
    { title: 'Dispatch', detail: 'per-level pipeline over stories; task.js per subtask', model: 'sonnet' },
    { title: 'Merge', detail: 'lock-serialized merge + full suite + close + board', model: 'haiku' },
    { title: 'Resolve', detail: 'conflict/test-failure resolution, capped at 3 attempts', model: 'opus' },
  ],
}

// ── orchestrator-core.mjs, inlined verbatim (harness cannot import a sibling
// .mjs from a Workflow script — see the "orchestrator.js inlines
// orchestrator-core verbatim" guard test in lib/orchestrator-core.test.mjs,
// which fails the whole test file if this block and that module drift apart) ──

// The `<n>` in an "L<layer>.<story>.<n>" title prefix — the intended sequence
// position of a subtask. Issue numbers only reflect milestone-setup's creation
// loop timing, so they are not a safe proxy for order.
function parseOrdinal(title) {
  const m = /L\d+\.\d+\.(\d+)/.exec(String(title ?? ''))
  return m ? Number(m[1]) : null
}

function orderSubtasks(subtasks) {
  return [...subtasks].sort((a, b) => {
    const oa = parseOrdinal(a.title)
    const ob = parseOrdinal(b.title)
    if (oa === null && ob === null) return a.number - b.number
    if (oa === null) return 1
    if (ob === null) return -1
    return oa - ob || a.number - b.number
  })
}

// Closed-and-merged is the ONLY done signal. A closed issue whose PR never
// merged (task.js did exactly this to #429) must read as remaining work, or
// the orchestrator would silently skip real work on resume.
function isSubtaskDone(subtask) {
  return String(subtask.state ?? '').toUpperCase() === 'CLOSED'
    && Boolean(subtask.pr && subtask.pr.merged === true)
}

function remainingSubtasks(story) {
  return orderSubtasks((story.subtasks ?? []).filter(s => !isSubtaskDone(s)))
}

function computeLevels(stories) {
  const doneNumbers = new Set(
    stories.filter(s => remainingSubtasks(s).length === 0).map(s => s.number),
  )
  const pending = stories
    .filter(s => !doneNumbers.has(s.number))
    .sort((a, b) => a.number - b.number)
  const pendingNumbers = new Set(pending.map(s => s.number))

  const levels = []
  const placed = new Set()
  let rest = pending
  while (rest.length > 0) {
    // A dep is satisfied when the upstream story has zero remaining subtasks
    // (it dropped out of `pending`) or was already placed in an earlier level.
    const ready = rest.filter(s => (s.blockedBy ?? [])
      .every(d => !pendingNumbers.has(d) || placed.has(d)))
    if (ready.length === 0) {
      throw new Error(`orchestrator: dependency cycle among stories ${rest.map(s => `#${s.number}`).join(', ')}`)
    }
    levels.push(ready)
    for (const s of ready) placed.add(s.number)
    rest = rest.filter(s => !placed.has(s.number))
  }
  return levels
}

// Orchestrator is one async control flow, so this is a plain in-script mutex,
// not a distributed lock. `.catch(() => {})` on the stored tail is essential:
// a failed merge must not jam every subsequent merge in the run.
function makeMergeLock() {
  let queue = Promise.resolve()
  return function withMergeLock(fn) {
    const next = queue.then(fn, fn)
    queue = next.catch(() => {})
    return next
  }
}

function escalation({ level, story, subtask, pr, trigger, baseBranch, attempts }) {
  if (trigger !== 'conflict' && trigger !== 'tests' && trigger !== 'blocked') {
    throw new Error(`orchestrator: unknown escalation trigger "${trigger}" (expected "conflict", "tests", or "blocked")`)
  }
  const message = trigger === 'blocked'
    ? `orchestrator STOPPED: subtask #${subtask} (story #${story}, level ${level}) could not be dispatched/verified against ${baseBranch} — no merge was attempted. ${(attempts ?? []).length} note(s) recorded.`
    : `orchestrator STOPPED: subtask #${subtask} (story #${story}, level ${level}) could not be merged into ${baseBranch} — trigger: ${trigger}. ${(attempts ?? []).length} resolution attempt(s) failed.`
  return {
    escalated: true, level, story, subtask, pr, trigger, baseBranch,
    attempts: attempts ?? [],
    message,
  }
}

// ── end inlined orchestrator-core.mjs ─────────────────────────────────────

const REPO = 'paulomtts/pyjinhx'
const REPO_DIR = '/home/mtts/Code/libs/pyjinhx'
// Merge + full-suite verification runs here, NOT in REPO_DIR: task.js's own
// Implement/PR stages run concurrently in REPO_DIR (git worktree add, git
// fetch, etc. from other stories' pipelines), so checking out baseBranch and
// running pytest there would race their git state. This directory is only
// ever touched from inside the merge lock, so reusing one path across merges
// is safe (never two writers at once).
const MERGE_WORKTREE = `${REPO_DIR}/.claude/worktrees/orchestrator-merge`
const PROJECT_ID = 'PVT_kwHOBZmM8c4BewiO'
const STATUS_FIELD_ID = 'PVTSSF_lAHOBZmM8c4BewiOzhZIXw8'
const DONE_OPTION_ID = 'a65ad310'
const MAX_RESOLVE_ATTEMPTS = 3

// ── args ─────────────────────────────────────────────────────────────────────
let raw = args
if (typeof raw === 'string') { try { raw = JSON.parse(raw) } catch { raw = { milestone: raw } } }
const opts = raw && typeof raw === 'object' ? raw : {}
const milestoneNumber = Number(opts.milestone ?? opts.milestoneNumber)
if (!Number.isInteger(milestoneNumber) || milestoneNumber <= 0) {
  throw new Error('orchestrator needs a milestone number, e.g. args: {"milestone": 7, "baseBranch": "l2-registry-assets"}')
}
// baseBranch is REQUIRED and never defaulted: nothing in this workflow or in
// milestone-setup maps a milestone to a branch, and task.js itself requires it.
const baseBranch = opts.baseBranch
if (typeof baseBranch !== 'string' || baseBranch.length === 0) {
  throw new Error('orchestrator needs a base branch, e.g. args: {"milestone": 7, "baseBranch": "l2-registry-assets"}')
}
// agent() caches on (prompt, opts) across a resumeFromRunId. Detect's prompt
// text is otherwise identical every invocation, so a resume would silently
// replay a stale GitHub snapshot from the run's FIRST Detect call instead of
// re-reading current state — exactly what happened resuming wf_7f27b75f-137
// after several levels had already merged. A caller-supplied nonce (required,
// since Date.now()/Math.random() are unavailable in workflow scripts) busts
// that cache key on every resume; pass a fresh value (e.g. current ISO time)
// each time this workflow is (re)launched.
const nonce = opts.nonce
if (typeof nonce !== 'string' || nonce.length === 0) {
  throw new Error('orchestrator needs a nonce to defeat Detect\'s resume cache, e.g. args: {"milestone": 7, "baseBranch": "...", "nonce": "<current timestamp>"}')
}

// ── 1. Detect (Haiku) — raw GitHub state only; levels computed in-script ────
phase('Detect')
const detected = await agent(`Detect the remaining work on pyjinhx milestone #${milestoneNumber}, in ${REPO_DIR}. Read state only — do NOT create, close, edit, comment on, or merge anything.

1. List the milestone's story issues:
   \`gh issue list --repo ${REPO} --milestone "<milestone title>" --label story --state all --json number,title,state\`
   (resolve the title first with \`gh api repos/${REPO}/milestones/${milestoneNumber} --jq .title\`).
2. For each story, get its blockedBy edges via GraphQL (\`issue { blockedBy(first:50) { nodes { number } } }\`). Report ONLY the numbers, no interpretation, and do NOT compute levels — that is done in-script.
3. For each story, list its sub-issues via \`gh api repos/${REPO}/issues/<story number>/sub_issues --jq '.[] | {number, title, state}'\` (the native GitHub sub-issue relation — do NOT use \`gh issue list --label subtask\`, which returns every subtask in the milestone with no link back to its parent story). Report number, title (VERBATIM, including the "L<layer>.<story>.<n>" prefix — ordering depends on it), and state.
4. For each subtask, find its linked PR STRICTLY by head branch — task.js always names the branch \`task-<issue number>\`: \`gh pr list --repo ${REPO} --head task-<issue number> --state all --json number,url,state,headRefName,mergedAt\`. Do NOT use free-text search (\`--search "<n> in:body"\` matches unrelated PRs whose body merely contains those digits). Accept a PR only if its headRefName is exactly \`task-<issue number>\`; otherwise treat the subtask as having no PR. Set pr to {url, state, merged} where merged is true ONLY if the PR's state is MERGED; null if there is no PR at all. Do not infer merged from the issue being closed.

Return the raw structure. No summarizing, no judging what is "done". [cache-buster, ignore: ${nonce}]`,
  { label: `detect:m${milestoneNumber}`, phase: 'Detect', model: 'haiku', schema: {
    type: 'object', required: ['stories'],
    properties: { stories: { type: 'array', items: {
      type: 'object', required: ['number', 'title', 'blockedBy', 'subtasks'],
      properties: {
        number: { type: 'integer' }, title: { type: 'string' },
        blockedBy: { type: 'array', items: { type: 'integer' } },
        subtasks: { type: 'array', items: {
          type: 'object', required: ['number', 'title', 'state'],
          properties: { number: { type: 'integer' }, title: { type: 'string' }, state: { type: 'string' },
            pr: { type: ['object', 'null'], properties: { url: { type: 'string' }, state: { type: 'string' }, merged: { type: 'boolean' } } } },
        } },
      },
    } } },
  } })
if (!detected) throw new Error('detect agent died')

const levels = computeLevels(detected.stories)
if (levels.length === 0) {
  return { milestone: milestoneNumber, baseBranch, done: true, reason: 'every story on this milestone is fully merged and closed' }
}

// ── merge lock + halt flag ──────────────────────────────────────────────────
const withMergeLock = makeMergeLock()
let halted = null   // set to an escalation payload; stops all new dispatch

// ── per-subtask stage ────────────────────────────────────────────────────────
async function runSubtask(levelIndex, story, subtask) {
  if (halted) return { subtask: subtask.number, skipped: 'halted' }

  let t
  if (subtask.pr && subtask.pr.url && subtask.pr.merged !== true && subtask.pr.state === 'OPEN') {
    // Resume case (the #429 incident): an open, unmerged PR already exists for
    // this subtask — task.js previously died after opening it. Re-invoking
    // task.js would fail (`git worktree add -b` on an existing branch, `gh pr
    // create` on a head that already has an open PR). Skip straight to merge.
    const prNumberMatch = /\/pull\/(\d+)/.exec(subtask.pr.url)
    t = {
      pr: prNumberMatch ? Number(prNumberMatch[1]) : subtask.pr.url,
      branch: `task-${subtask.number}`,
      plan: '(resumed subtask: task.js already opened this PR in a prior run; original plan text is not available here)',
    }
  } else {
    // a. task.js opens the PR and stops (orchestrated mode). task.js can
    // throw (e.g. "pr agent died") instead of returning — catch it so a dead
    // agent halts the run rather than vanishing into pipeline()'s
    // Promise.allSettled and letting the next level start anyway.
    let tResult = null
    let thrown = null
    try {
      tResult = await workflow('task', { issue: subtask.number, baseBranch, mode: 'orchestrated' })
    } catch (err) {
      thrown = err
    }
    if (thrown) {
      halted = escalation({
        level: levelIndex, story: story.number, subtask: subtask.number, pr: null, baseBranch,
        trigger: 'blocked',
        attempts: [{ attempt: 0, resolved: false, detail: `task workflow threw: ${thrown && thrown.message ? thrown.message : thrown}` }],
      })
      return { subtask: subtask.number, escalated: true }
    }
    if (!tResult || tResult.refused || tResult.blocked || !tResult.pr) {
      // Only an actual `blocked: 'tests'` result is a real test failure; a
      // validation blocker or refusal never attempted a merge at all.
      const trigger = tResult && tResult.blocked === 'tests' ? 'tests' : 'blocked'
      halted = escalation({
        level: levelIndex, story: story.number, subtask: subtask.number, pr: tResult && tResult.pr, baseBranch,
        trigger,
        attempts: [{ attempt: 0, resolved: false, detail: `task workflow did not produce a PR: ${JSON.stringify(tResult)}` }],
      })
      return { subtask: subtask.number, escalated: true }
    }
    t = tResult
  }
  // t === { issue, pr, branch, plan, tests }; card is at "In review", issue OPEN.

  // b-e. Merge attempt, full-suite verification, and (if needed) up to
  // MAX_RESOLVE_ATTEMPTS Opus resolve attempts — ALL inside ONE lock
  // acquisition. Nesting a second withMergeLock call inside this callback
  // would self-deadlock (the queued `.then` can never resolve while the
  // outer callback that owns the queue slot is still awaiting it), so the
  // resolve loop below calls `agent()` directly, not withMergeLock again.
  // (No phase() call here: stories run concurrently under pipeline(), and
  // phase() mutates global transcript-grouping state — calling it from a
  // concurrent stage would interleave unreadably across stories.)
  let settlement
  try {
    settlement = await withMergeLock(async () => {
      const m = await agent(`Merge PR ${t.pr} (branch ${t.branch}) into ${baseBranch} for pyjinhx subtask #${subtask.number}. You hold an exclusive merge lock — no other merge runs concurrently. IMPORTANT: do all of this in the dedicated merge worktree below, NOT in ${REPO_DIR} directly — other stories' task.js runs may have that checkout on an unrelated branch at any moment.

0. Set up the dedicated merge worktree pinned to ${baseBranch}: from ${REPO_DIR}, run \`git fetch origin\`, then \`git worktree add ${MERGE_WORKTREE} ${baseBranch} 2>/dev/null || true\`; then \`cd ${MERGE_WORKTREE} && git fetch origin && git checkout ${baseBranch} && git reset --hard origin/${baseBranch}\`. All remaining steps run from ${MERGE_WORKTREE} unless noted (gh pr commands are location-independent).
1. Poll \`gh pr checks ${t.pr} --watch\` until CI finishes (or poll \`gh pr checks ${t.pr}\` every ~30s).
2. If any check fails, do NOT merge and do NOT close the issue — return merged=false, conflict=false, detail=<failing check names + output>.
3. \`gh pr merge ${t.pr} --squash --delete-branch\`. If it reports a conflict, return merged=false, conflict=true, detail=<the conflicting paths>.
4. \`gh pr merge\`'s exit code is NOT proof of a merge. Verify independently: \`gh pr view ${t.pr} --json state,mergeCommit\` must show state exactly "MERGED" and a non-null mergeCommit. If it does not, return merged=false with what gh actually showed, and do NOT close the issue under any circumstances.
5. Only after that verification: in ${MERGE_WORKTREE}, \`git fetch origin && git reset --hard origin/${baseBranch}\` and run the FULL suite: \`uv run pytest tests/ -q\`. If it is red, return merged=true, suiteGreen=false, detail=<failures>. Do NOT close the issue.
6. If the suite is green: \`gh issue close ${subtask.number} --comment "Merged via ${t.pr} into ${baseBranch}."\` then move its Project 12 card to Done and mirror the parent story:
   a. Find the card: \`ITEM_ID=$(gh api graphql -f query='query($n:Int!){repository(owner:"paulomtts",name:"pyjinhx"){issue(number:$n){projectItems(first:10){nodes{id project{id}}}}}}' -F n=${subtask.number} --jq '.data.repository.issue.projectItems.nodes[] | select(.project.id=="${PROJECT_ID}") | .id')\`
   b. Set its Status to Done: \`gh api graphql -f query='mutation($i:ID!,$o:String!){updateProjectV2ItemFieldValue(input:{projectId:"${PROJECT_ID}",itemId:$i,fieldId:"${STATUS_FIELD_ID}",value:{singleSelectOptionId:$o}}){projectV2Item{id}}}' -f i="$ITEM_ID" -f o="${DONE_OPTION_ID}"\` (pass -f, not -F, for the option id).
   c. Mirror the parent story #${story.number}: check its remaining sub-issues' Status (missing value counts as Backlog). If EVERY sub-issue is Done, set the story's card to Done too (same mutation, option id ${DONE_OPTION_ID}) and, if the story issue is still OPEN, close it with \`gh issue close ${story.number} --comment "All sub-issues merged into ${baseBranch}. Story complete."\`. Otherwise leave the story's card as-is (its own Status already reflects In progress from earlier task.js runs).

Do NOT close the issue unless steps 4 and 5 both verified success. Return merged, conflict, suiteGreen, closed, detail.`,
        { label: `merge:#${subtask.number}`, phase: 'Merge', model: 'haiku', schema: {
          type: 'object', required: ['merged', 'conflict', 'suiteGreen', 'closed', 'detail'],
          properties: { merged: { type: 'boolean' }, conflict: { type: 'boolean' },
            suiteGreen: { type: 'boolean' }, closed: { type: 'boolean' }, detail: { type: 'string' } },
        } })
      if (!m) throw new Error(`merge agent died on #${subtask.number}`)

      if (m.merged && m.suiteGreen && m.closed) {
        return { done: true, subtask: subtask.number, merged: true, pr: t.pr }
      }

      // Merge + suite both succeeded but the close/board step failed — this
      // is bookkeeping, not a test failure. One cheap retry, not an Opus
      // resolve attempt (there's no code to fix and nothing to diagnose).
      if (m.merged && m.suiteGreen && !m.closed) {
        const c = await agent(`The merge of PR ${t.pr} into ${baseBranch} for pyjinhx subtask #${subtask.number} succeeded and the full suite was green, but closing the issue / moving the board card failed: ${m.detail}. Retry ONLY that bookkeeping: \`gh issue close ${subtask.number} --comment "Merged via ${t.pr} into ${baseBranch}."\`, then the Project 12 Done move + parent-story mirror (same project/field/option ids as before: project ${PROJECT_ID}, field ${STATUS_FIELD_ID}, Done option ${DONE_OPTION_ID}). Do NOT touch git, code, or CI. Return closed=true/false and detail.`,
          { label: `close-retry:#${subtask.number}`, phase: 'Merge', model: 'haiku', schema: {
            type: 'object', required: ['closed', 'detail'],
            properties: { closed: { type: 'boolean' }, detail: { type: 'string' } },
          } })
        if (c && c.closed) return { done: true, subtask: subtask.number, merged: true, pr: t.pr }
        return { done: false, trigger: 'blocked', outcome: m, attempts: [{ attempt: 0, resolved: false, detail: `merge+suite succeeded but close/board bookkeeping failed twice: ${c ? c.detail : 'close-retry agent died'}` }] }
      }

      // d/e → Resolve (Opus), capped at MAX_RESOLVE_ATTEMPTS, still inside
      // this same lock acquisition (it's finishing the same merge).
      const trigger = m.conflict ? 'conflict' : 'tests'
      const attempts = []
      for (let attempt = 1; attempt <= MAX_RESOLVE_ATTEMPTS; attempt++) {
        if (halted) break
        const r = await agent(`Resolve a ${trigger === 'conflict' ? 'merge conflict' : 'post-merge test failure'} for pyjinhx subtask #${subtask.number} (PR ${t.pr}, branch ${t.branch}) against ${baseBranch}. Attempt ${attempt} of ${MAX_RESOLVE_ATTEMPTS}. You hold the exclusive merge lock.

What happened: ${m.detail}
${attempts.length ? `Previous attempts:\n${attempts.map(a => `- attempt ${a.attempt}: ${a.detail}`).join('\n')}` : ''}
Plan for this subtask: ${t.plan}

You have FULL autonomy in a scratch worktree (\`git worktree add ${REPO_DIR}/.claude/worktrees/resolve-${subtask.number} ...\`):
- Read BOTH sides' intent — the subtask's plan/spec and the code the other branch landed — do not just diff and pick a side. Two branches can each be individually correct and still need a synthesized third design (see the da123cd merge on l2-registry-assets).
- Edit code freely; you are NOT limited to deleting conflict markers. Change signatures, unify plumbing, update BOTH sides' call sites and tests if that is what the merged design needs.
- Rerun \`uv run pytest tests/ -q\` until green, plus \`uvx basedpyright pyjinhx2/ tests/pyjinhx2/\` and \`uvx ruff@0.16.0 check .\` / \`format --check .\`.
- Commit granularly, ending each message with:
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
- Then complete the merge into ${baseBranch}, verify it the same way (\`gh pr view ${t.pr} --json state,mergeCommit\` must show MERGED + non-null mergeCommit, OR ${baseBranch} must contain your merge commit), re-run the full suite on ${baseBranch}, and only then \`gh issue close ${subtask.number} --comment "Merged via ${t.pr} into ${baseBranch}."\` and move its Project 12 card to Done (same project/field/option ids as the merge step above).

Never weaken, skip, or delete a test to make the suite green — that is an automatic failure of this attempt. Return resolved=true only if the merge is verified, the full suite is green, and the issue is closed. Otherwise resolved=false with exactly what you tried and why it failed.`,
          { label: `resolve:#${subtask.number}:${attempt}`, phase: 'Resolve', model: 'opus', schema: {
            type: 'object', required: ['resolved', 'detail'],
            properties: { resolved: { type: 'boolean' }, detail: { type: 'string' } },
          } })
        attempts.push({ attempt, resolved: Boolean(r && r.resolved), detail: r ? r.detail : 'resolve agent died' })
        if (r && r.resolved) return { done: true, subtask: subtask.number, merged: true, resolvedIn: attempt, pr: t.pr }
      }

      return { done: false, trigger, outcome: m, attempts }
    })
  } catch (err) {
    halted = escalation({
      level: levelIndex, story: story.number, subtask: subtask.number, pr: t.pr, baseBranch,
      trigger: 'blocked',
      attempts: [{ attempt: 0, resolved: false, detail: `merge lock callback threw: ${err && err.message ? err.message : err}` }],
    })
    return { subtask: subtask.number, escalated: true }
  }

  if (settlement.done) {
    const { done, ...result } = settlement
    return result
  }

  if (halted) return { subtask: subtask.number, skipped: 'halted' }
  halted = escalation({ level: levelIndex, story: story.number, subtask: subtask.number, pr: t.pr, trigger: settlement.trigger, baseBranch, attempts: settlement.attempts ?? [] })
  return { subtask: subtask.number, escalated: true }
}

// ── level loop + pipeline() barrier ─────────────────────────────────────────
const results = []
for (let i = 0; i < levels.length; i++) {
  if (halted) break
  phase('Dispatch')
  const level = levels[i]
  // pipeline(items, ...stages) — the harness global — takes the items array
  // as its first argument and one stage function per remaining arg; it is
  // NOT pipeline(arrayOfRunnables). One story per item; a story's own
  // subtasks are sequential inside its single stage function.
  const levelResults = await pipeline(level, async story => {
    const out = []
    for (const subtask of remainingSubtasks(story)) {
      if (halted) { out.push({ subtask: subtask.number, skipped: 'halted' }); continue }
      out.push(await runSubtask(i, story, subtask))
    }
    return { story: story.number, subtasks: out }
  })
  // pipeline() uses Promise.allSettled internally and maps a rejected/dead
  // stage to `null` rather than propagating — treat that as a halt too, or
  // Level N+1 would dispatch on top of a level that never actually finished.
  if (levelResults.some(r => r === null || r === undefined) && !halted) {
    halted = {
      escalated: true, level: i, story: null, subtask: null, pr: null, trigger: 'blocked', baseBranch,
      attempts: [],
      message: `orchestrator STOPPED: level ${i} had a story pipeline stage die (returned null from pipeline()) with no escalation payload set — treating as a hard halt.`,
    }
  }
  results.push({ level: i, stories: levelResults })
}

// ── return ───────────────────────────────────────────────────────────────
// Escalation is returned, not thrown, so the payload reaches the top-level
// session structurally and intact. `halted` only stops NEW dispatch —
// in-flight stages in the current level finish naturally (they're already
// awaited by pipeline()), per the spec's non-goal on forced teardown.
if (halted) return { milestone: milestoneNumber, baseBranch, ...halted, completed: results }
return { milestone: milestoneNumber, baseBranch, done: true, levels: levels.length, completed: results }

