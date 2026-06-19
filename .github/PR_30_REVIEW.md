# PR-30 Code Review

## Scope

- PR: PR-30
- Branch: `codex/pr-30-risk-portfolio-ui`
- Base: `codex/pr-29-backtest-results-ui`
- Files reviewed:
  - `frontend/src/pages/RiskPortfolio.tsx`
  - `frontend/src/pages/__tests__/RiskPortfolio.test.tsx`
  - `frontend/src/lib/api.ts`
  - `frontend/src/router.tsx`
  - `scripts/acceptance-pr-30`
  - `.github/PR_30_ACCEPTANCE.md`

## Review Summary

```text
Decision: approve
```

## Blocker

- None

## Important

- None

## Follow-up

- Add a dedicated trade-plan page in the next PR so strategy-level allocation and stock-level target positions can be reviewed in a deeper workflow.

## Required Checks

- [x] The PR stays inside the current local Git project.
- [x] The new UI is Chinese.
- [x] The PR does not introduce `OPENAI_API_KEY`.
- [x] The PR does not add JoinQuant login, browser automation, remote submission, approval, draft signal generation, live authorization, runner start, broker actions, or live trading.
- [x] Targeted PR-30 acceptance passed.
- [x] Previous PR acceptance passed.
- [x] Backend compile check passed.
- [x] Frontend full test suite passed.
- [x] Frontend build passed.
- [x] Automated smoke test passed.

## Review Checklist

| Area | Result | Evidence |
| --- | --- | --- |
| Scope control | Pass | PR-30 adds a single risk-portfolio page, typed API wiring, route wiring, and targeted tests |
| UI language | Pass | Page title, controls, actions, validation errors, and guardrail copy are Chinese |
| API wiring | Pass | Frontend calls allocation, allocation-list, and trade-plan routes through typed API methods |
| Research boundary | Pass | UI only creates allocation/trade-plan drafts and does not approve signals or submit broker actions |
| Failure handling | Pass | Invalid local parameters and Chinese backend prerequisite errors render directly in the page |
| Automated acceptance | Pass | `scripts/acceptance-pr-30` covers render, allocation, refresh, draft trade plan, validation, navigation, and guardrails |

## Verification Evidence

```text
bash scripts/acceptance-pr-30
12 tests passed; PR-30 acceptance passed.

bash scripts/acceptance-pr-29
11 tests passed; PR-29 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run test:run
31 test files passed; 259 tests passed.

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
