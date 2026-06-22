# PR-22 Acceptance Cases

## Scope

- PR: PR-22
- Branch: `codex/pr-22-daily-research-workflow`
- Feature area: Manual daily A-share research workflow orchestration

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-22
```

Expected result:

```text
PR-22 acceptance passed.
```

## Baseline Smoke Command

Command:

```bash
bash scripts/smoke
```

Expected result:

```text
PR smoke test passed.
```

## Targeted Acceptance Cases

| Case ID | Scenario | Steps | Expected Result | Automated Command |
| --- | --- | --- | --- | --- |
| PR-22-001 | Dry-run planning | Run `/api/daily-workflow/run` with `dry_run=true` and selected steps | Response lists planned steps, returns `research_only=true`, and keeps `live_trading=false` | `bash scripts/acceptance-pr-22` |
| PR-22-002 | Full local research chain | Seed local test行情, submit one AI产业链 policy document, and run all workflow steps | Events, mappings, sector scores, candidates, backtests, rankings, allocation, and draft signals are generated locally | `bash scripts/acceptance-pr-22` |
| PR-22-003 | Missing prerequisites | Run `build_candidates` on an empty local store | Workflow returns `blocked` with a Chinese prerequisite message and does not continue silently | `bash scripts/acceptance-pr-22` |
| PR-22-004 | Step validation | Request an unsupported step such as `approve_plan` | API returns a Chinese 400 validation error | `bash scripts/acceptance-pr-22` |
| PR-22-005 | Cost and trading guardrails | Inspect the PR-22 workflow implementation | No `OPENAI_API_KEY`, browser automation, JoinQuant remote submission, plan approval, export package, broker action, or live trading path is introduced | `bash scripts/acceptance-pr-22` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-22
6 tests passed; PR-22 acceptance passed.
```

Full verification evidence is recorded in `PR_22_REVIEW.md`.
