# PR-36 Acceptance Cases

## Scope

- PR: PR-36
- Branch: `codex/pr-36-full-flow-browser-qa`
- Feature area: Full local browser QA for the AI industry-chain A-share workflow

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-36
```

Expected result:

```text
PR-36 browser full-flow QA passed.
PR-36 acceptance passed.
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
| PR-36-001 | Start a clean local QA environment | Run `bash scripts/acceptance-pr-36` | A temporary `ASHARE_DATA_ROOT` is created, backend and frontend dev servers start, and browser QA uses that isolated store | `bash scripts/acceptance-pr-36` |
| PR-36-002 | Open the product shell in a real browser | Browser navigates through dashboard, data sources, strategy lab, backtest results, risk portfolio, trade plan, and JoinQuant export | All pages render Chinese UI without page errors | `bash scripts/acceptance-pr-36` |
| PR-36-003 | Run the AI industry-chain research task | Browser opens `/daily-workflow`, inputs `AI 产业链事件跟踪`, runs dry-run and full run | Workflow completes all 11 steps, writes 8 local backtests, 3 draft signals, and event-reaction evidence | `bash scripts/acceptance-pr-36` |
| PR-36-004 | Verify strategy and backtest pages | Browser opens strategy lab and backtest results, then refreshes runs/rankings | UI shows 8 local backtest runs and 8 strategy rankings | `bash scripts/acceptance-pr-36` |
| PR-36-005 | Verify risk and trade-plan pages | Browser opens risk portfolio and trade plan | UI shows 5 strategy allocations, 3 target positions, and simulation-only approval status | `bash scripts/acceptance-pr-36` |
| PR-36-006 | Generate JoinQuant-compatible copy package | Browser opens JoinQuant export, preflights approved simulated signals, generates and downloads the local copy package | Package includes `strategy.py`, `signals.json`, `signals.csv`, and `README.md`; no external JoinQuant login or order submission occurs | `bash scripts/acceptance-pr-36` |
| PR-36-007 | Preserve cost and trading guardrails | Inspect automation and runtime checks | The flow uses Codex OAuth/provider guardrails, does not introduce model API keys, and remains research/simulation only | `bash scripts/acceptance-pr-36` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-36
PR-36 browser full-flow QA passed.
{"approved_signals": 3, "backtest_runs": 8, "joinquant_package_files": ["README.md", "signals.csv", "signals.json", "strategy.py"], "task": "AI 产业链事件跟踪", "workflow_date": "2026-06-24"}
PR-36 acceptance passed.
```

Full verification evidence is recorded in `PR_36_REVIEW.md`.
