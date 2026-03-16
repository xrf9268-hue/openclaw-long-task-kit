# Loop Job Configuration

Automated issue processing loop for `xrf9268-hue/openclaw-long-task-kit`.
This job runs inside a Claude Code session via `CronCreate` and auto-expires
after 3 days.

## Cron Schedule

```
*/30 2-19 * * 1-5
```

| Field | Value | Meaning |
|-------|-------|---------|
| Minute | `*/30` | Every 30 minutes |
| Hour | `2-19` | UTC 02:00–19:59 |
| Day of month | `*` | Every day |
| Month | `*` | Every month |
| Day of week | `1-5` | Monday–Friday |

### Time Zone Mapping

| Time Zone | Job Window | Peak (1x) Window |
|-----------|------------|-------------------|
| UTC | 02:00–19:59 | 12:00–18:00 |
| Beijing (UTC+8) | 10:00–03:59(+1) | 20:00–02:00(+1) |
| PT (PDT, UTC-7) | 19:00(prev)–12:59 | 05:00–11:00 |

The job window is designed to **fully avoid** the Claude 1x peak period
(weekdays 5–11am PT / 12–6pm GMT), maximizing 2x usage bonus.

> **DST note**: During PST (November–March), peak shifts to Beijing
> 21:00–03:00.  If recreating the job in winter, change the hour range to
> `3-19` to avoid the 02:00–02:59 overlap.

## Full Prompt

```markdown
## Automated Issue Processing Loop

### Step 1: Process Open PRs (must clear all before Step 2)

Run `gh pr list --repo xrf9268-hue/openclaw-long-task-kit --state open
--json number,title,headRefName,statusCheckRollup,reviewDecision,mergeable`
to check all open PRs:

**A. CI failure ->** `gh run view` to check logs, switch to the branch,
fix, push.

**B. Code review handling (by priority):**
- Fetch comments via `gh api repos/.../pulls/<N>/comments` and
  `gh api repos/.../pulls/<N>/reviews`
- **P0/P1 (bugs, security, logic errors) ->** Must fix, push update
- **P2 (code quality, naming, suggestions) ->** Evaluate: if the change
  is clear and safe, fix it; if it involves design decisions or
  uncertainty, **report to user and skip the PR**
- **P3/P4 (style preferences, optional suggestions) ->** Note but do not
  block merge

**C. Merge conflicts ->** Rebase onto main, push.

**D. Merge-ready PR (all CI SUCCESS + reviewDecision not
CHANGES_REQUESTED + no conflicts + no unresolved P0-P2 comments):**
- `gh pr merge <N> --repo xrf9268-hue/openclaw-long-task-kit --squash
  --delete-branch`
- Clean up local branch, `git checkout main && git pull`

**E. Process all PRs before entering Step 2.**

### Step 2: Select Next Issue

`git checkout main && git pull` to ensure latest.

Run `gh issue list --repo xrf9268-hue/openclaw-long-task-kit --state open
--json number,title,labels --limit 50`.

**Exclude:** issues with existing open PRs, #3 (vision/roadmap),
#6 (external research reference).

**Sort by M0 > M1 > M2 > M3 priority, Size S > M > L.**
For issues without a Size label, read the issue body
(`gh issue view <N> --repo ...`) to assess complexity first.

If no processable issues remain, report "all issues completed" or
"remaining issues need human decision".

### Step 3: Classify & Implement

After reading the issue body, handle by category:

**A. Issues with clear AC or concrete improvement suggestions
(e.g. #7, #13, #18):**
- Size S/M -> Direct TDD
- Size L (clear AC) -> Direct TDD
- Size L (needs architecture decisions) -> Plan mode, pause for user
  confirmation

**B. Strongly related issue groups (e.g. #8-#12 state machine):**
- Do not implement individually; assess overall architectural impact
- Enter Plan mode, design a thin-wrapper solution per AGENTS.md
  constraints
- Pause for user confirmation

**C. Quality requirements (rocket-grade standards):**
- Strict TDD: write failing test -> verify red -> minimal implementation
  -> verify green
- Every behavior change must have test coverage
- Update README.md when adding CLI commands or changing output
- Follow all AGENTS.md constraints: thin wrapper, stdlib-first, strict
  mypy, no speculative abstractions
- Changes must be small and reviewable; one PR does one thing

### Step 4: Verify & Submit

Full check suite (all must pass):

    .venv/bin/pytest -q
    .venv/bin/ruff check .
    .venv/bin/ruff format --check src/ tests/
    .venv/bin/mypy --strict src tests

After passing, commit and create PR (body includes `Closes #<number>`).

**One issue per loop iteration. Wait for next cycle to verify CI/review.**

Report results: which PRs were merged, which new PR was created, which
reviews were fixed, or which reviews need user decision.
```

## Design Rationale

### Why 30-minute intervals?

- **Sufficient for Size S/M issues**: Most small issues complete within a
  single 30-minute window (TDD cycle + verification + PR creation).
- **Natural checkpoint for CI**: After creating a PR, the next iteration
  checks whether CI passed and reviews arrived.
- **Prevents runaway work**: Forces a stop-and-check cadence instead of
  continuous implementation.

### Why one issue per iteration?

- **Avoids context contamination**: Each issue gets a clean `main` base.
- **Enables review feedback loops**: PRs get time for CI and reviewer
  comments before the next issue starts.
- **Keeps PRs small and reviewable**: Aligns with AGENTS.md "small and
  reviewable" requirement.

### Why process PRs before new issues?

- **Prevents PR pile-up**: Without this rule, the loop would keep creating
  PRs without merging, leading to merge conflicts and stale branches.
- **Review-first culture**: Code review feedback is more valuable fresh;
  addressing it promptly improves code quality.
- **Clean main branch**: Merging before starting new work ensures each
  issue builds on the latest integrated code.

### Why priority-based code review handling?

Prior experience showed two failure modes:

1. **Blind compliance**: Treating every bot comment as a blocking issue led
   to unnecessary churn on P3/P4 style suggestions.
2. **Blind ignore**: Skipping reviews entirely caused real bugs (P1) to
   ship, e.g. incorrect remediation guidance in README.

The P0-P4 classification balances thoroughness with pragmatism:

- P0/P1 must be fixed (safety).
- P2 requires judgment (report to user if uncertain).
- P3/P4 are non-blocking (note but don't delay).

### Why exclude only #3 and #6?

Early versions of the loop excluded issues #7-#13 as "discussion-only".
This was corrected: these issues contain **concrete improvement
suggestions** that serve as acceptance criteria.  Only two issues are truly
non-implementable:

- **#3**: Meta vision/roadmap with open-ended product questions.
- **#6**: External research report reference with no code work.

### Why Plan mode for #8-#12?

Issues #8-#12 form a coherent group around state-machine workflow
improvements (repair lanes, transition guards, automatic handoffs).
Implementing them piecemeal would risk:

- Contradictory designs across PRs.
- Violating AGENTS.md "thin wrapper" constraint by accidentally building a
  workflow engine.
- Rework when later issues invalidate earlier implementations.

Plan mode forces upfront architectural alignment before any code is written.
