# PR-36 Code Review

## Scope

- PR: PR-36
- Branch: `codex/pr-36-full-flow-browser-qa`
- Base: `codex/pr-35-data-sources-ui`
- Files reviewed:
  - `scripts/pr36_browser_full_flow.py`
  - `scripts/acceptance-pr-36`
  - `.github/PR_36_ACCEPTANCE.md`

## Review Summary

```text
Decision: approve
```

## Blocker

- None

## Important

- External JoinQuant account login and cloud backtest execution are intentionally not automated. This PR verifies local generation of a JoinQuant-compatible strategy package and local A-share backtest flow.

## Follow-up

- Add optional user-guided JoinQuant cloud import instructions later if the user wants a manual checklist for their own logged-in JoinQuant workspace.

## Required Checks

- [x] The PR stays inside the current local Git project.
- [x] The browser QA opens the local app through a real Chromium browser.
- [x] The AI industry-chain task runs through the daily workflow.
- [x] Local strategy backtests and rankings are generated and visible.
- [x] Risk allocation and trade-plan pages are verified.
- [x] JoinQuant-compatible strategy package is generated and downloaded locally.
- [x] The PR does not introduce model API key requirements.
- [x] The PR does not add JoinQuant login, browser automation against external JoinQuant, remote submission, live authorization, runner start, broker actions, or live trading.
- [x] Targeted PR-36 acceptance passed.
- [x] Previous PR acceptance passed.
- [x] Backend compile check passed.
- [x] Frontend full test suite passed.
- [x] Frontend build passed.
- [x] Automated smoke test passed.

## Review Checklist

| Area | Result | Evidence |
| --- | --- | --- |
| Scope control | Pass | PR-36 adds QA automation and documentation only |
| Environment isolation | Pass | Browser QA uses a temporary `ASHARE_DATA_ROOT` |
| Browser coverage | Pass | Dashboard, data sources, workflow, strategy, backtest, risk, trade plan, and JoinQuant export pages are opened |
| AI task flow | Pass | Browser inputs and runs `AI 产业链事件跟踪` |
| Backtest proof | Pass | Workflow produces 8 local backtests and 8 rankings |
| JoinQuant package proof | Pass | Local copy package includes strategy and signal files |
| Cost boundary | Pass | No new model API key requirement is introduced |
| Trading boundary | Pass | Flow remains research/simulation only |
| Automated acceptance | Pass | `scripts/acceptance-pr-36` passed |

## Verification Evidence

```text
bash scripts/acceptance-pr-36
PR-36 browser full-flow QA passed.
approved_signals=3; backtest_runs=8; package files=README.md, signals.csv, signals.json, strategy.py
PR-36 acceptance passed.

bash scripts/acceptance-pr-35
11 tests passed; PR-35 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

.venv/bin/python -m py_compile scripts/pr36_browser_full_flow.py
passed

npm --prefix frontend run test:run
33 test files passed; 271 tests passed.

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
