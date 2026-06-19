# PR-20 Acceptance Cases

## Scope

- PR: PR-20
- Branch: `codex/pr-20-simulation-readiness-report`
- Feature area: JoinQuant simulation-readiness report backend

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-20
```

Expected result:

```text
PR-20 acceptance passed.
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
| PR-20-001 | Clean simulation readiness | Seed approved signals, clean JoinQuant reports, and acceptable backtest drawdown | Report returns `ready`, `continue_simulation`, no failed executions, and `live_trading=false` | `bash scripts/acceptance-pr-20` |
| PR-20-002 | Observation window too short | Seed only one execution batch while requiring more batches | Report returns `needs_more_data` and recommends extending observation | `bash scripts/acceptance-pr-20` |
| PR-20-003 | Execution and risk issues | Seed rejected report, weight deviation, limit-up message, and high backtest drawdown | Report returns `needs_review` and `fix_before_live` with Chinese findings | `bash scripts/acceptance-pr-20` |
| PR-20-004 | API round trip | Call `/api/joinquant/simulation-readiness` after importing execution reports | API returns readiness score, checks, findings, totals, rates, and research-only guardrails | `bash scripts/acceptance-pr-20` |
| PR-20-005 | Route registration | Inspect FastAPI route table | Simulation-readiness route is mounted | `bash scripts/acceptance-pr-20` |
| PR-20-006 | Cost and trading guardrails | Inspect JoinQuant adapter and route files | No `OPENAI_API_KEY`, JoinQuant login automation, browser automation, or live order flow is introduced | `bash scripts/acceptance-pr-20` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-20
16 tests passed; PR-20 acceptance passed.
```

Full verification evidence is recorded in `PR_20_REVIEW.md`.
