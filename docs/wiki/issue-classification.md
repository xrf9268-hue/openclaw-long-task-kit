# Issue Classification

How the automated loop categorizes and prioritizes open issues.

## Priority Order

Issues are processed in milestone order, then by size within each
milestone:

```
M0-stability > M1-issue-loop > M2-github-e2e > M3-release
```

Within each milestone: **Size S > Size M > Size L**.

Issues without a Size label are evaluated by reading the issue body before
assignment.

## Classification Categories

### Skip Entirely

These issues are excluded from automated processing:

| Issue | Reason |
|-------|--------|
| #3 | Meta vision/roadmap with multiple open-ended questions requiring human decisions |
| #6 | External research report reference with no actionable code work |

### Direct TDD

Issues with concrete suggestions or clear acceptance criteria.  Implement
directly using strict TDD:

| Issue | Title | Milestone |
|-------|-------|-----------|
| #7 | Preflight bootstrap gap: init alone mistaken for preflight pass | M0 |
| #13 | Patrol should escalate preflight PASS but state still stuck | M0 |
| #18 | Unify diagnostics event model (Size L, may need Plan) | M0 |
| #24 | Document incident/pitfall reporting workflow in README | M1 |
| #26 | Implement `ltk report issue` command | M1 |
| #31 | Add sanitization strategy for paths, tokens, and URLs | M1 |

### Plan First

Issues that are interconnected or require architectural decisions before
implementation:

| Issue Group | Title Pattern | Reason |
|-------------|---------------|--------|
| #8, #9, #10, #11, #12 | State-machine workflow improvements | Form a coherent group around stage-gated transitions.  Must respect AGENTS.md thin-wrapper constraint.  Plan should propose minimal state/command additions. |

### RFC / Discussion

Issues that describe future direction rather than immediate work:

| Issue | Title | Action |
|-------|-------|--------|
| #23 | RFC: v0.4 auto-fetch issues and apply fixes | Read body to determine if actionable; if pure RFC, skip |

### Other Implementable Issues

Remaining issues by milestone.  Read issue body to determine approach:

| Milestone | Issues |
|-----------|--------|
| M2 | #22 (contract tests), #25 (CodeQL/CI), #29 (GitHub API client), #30 (fake openclaw binary) |
| M3 | #21 (release workflow), #27 (version tags), #28 (documentation), #32 (schema\_version) |

## Decision Flow

```
Issue opened
  |
  +-- #3 or #6? --> SKIP
  |
  +-- Has open PR? --> SKIP (wait for PR to merge)
  |
  +-- Part of #8-#12 group? --> PLAN MODE (group architecture)
  |
  +-- Has Size label?
  |     +-- S/M --> DIRECT TDD
  |     +-- L
  |           +-- AC clear? --> DIRECT TDD
  |           +-- Needs arch decision? --> PLAN MODE
  |
  +-- No Size label --> READ BODY --> assess complexity --> assign category
```

## Notes

- **"No AC" does not mean "skip"**: Many issues describe problems with
  detailed "Suggested improvements" sections that serve as acceptance
  criteria.  Always read the issue body before deciding.
- **New issues**: Issues created after this classification was written
  should be evaluated by reading their body.  Do not assume they fit
  existing categories.
- **Milestone labels**: Issues without milestone labels are treated as
  lowest priority (after M3).
