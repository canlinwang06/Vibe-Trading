# PR-31 Code Review

## Scope

- PR: PR-31
- Branch: `codex/pr-31-trade-plan-ui`
- Base: `codex/pr-30-risk-portfolio-ui`
- Files reviewed:
  - `frontend/src/pages/TradePlan.tsx`
  - `frontend/src/pages/__tests__/TradePlan.test.tsx`
  - `frontend/src/router.tsx`
  - `scripts/acceptance-pr-31`
  - `.github/PR_31_ACCEPTANCE.md`

## Review Summary

```text
Decision: approve
```

## Blocker

- None

## Important

- None

## Follow-up

- Add JoinQuant copy/export review in a later PR, with draft-only restrictions preserved until a simulation approval workflow is explicitly accepted.

## Required Checks

- [x] The PR stays inside the current local Git project.
- [x] The new UI is Chinese.
- [x] The PR does not introduce `OPENAI_API_KEY`.
- [x] The PR does not add JoinQuant login, browser automation, remote submission, approval, draft signal generation, live authorization, runner start, broker actions, or live trading.
- [x] Targeted PR-31 acceptance passed.
- [x] Previous PR acceptance passed.
- [x] Backend compile check passed.
- [x] Frontend full test suite passed.
- [x] Frontend build passed.
- [x] Automated smoke test passed.

## Review Checklist

| Area | Result | Evidence |
| --- | --- | --- |
| Scope control | Pass | PR-31 replaces the trade-plan placeholder with a read-only draft review page and tests |
| UI language | Pass | Page title, controls, table labels, validation errors, and guardrail copy are Chinese |
| API wiring | Pass | Frontend reads trade-plan data through the existing typed portfolio-risk API method |
| Research boundary | Pass | UI reviews draft plans only and does not approve, generate signals, export, or submit orders |
| Failure handling | Pass | Invalid local parameters and Chinese backend prerequisite errors render directly in the page |
| Automated acceptance | Pass | `scripts/acceptance-pr-31` covers render, plan refresh, target positions, strategy sources, validation, navigation, and guardrails |

## Verification Evidence

```text
bash scripts/acceptance-pr-31
11 tests passed; PR-31 acceptance passed.

bash scripts/acceptance-pr-30
12 tests passed; PR-30 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run test:run
32 test files passed; 264 tests passed.

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
