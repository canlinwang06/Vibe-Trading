# PR-28 Code Review

## Scope

- PR: PR-28
- Branch: `codex/pr-28-strategy-lab-ui`
- Base: `codex/pr-27-candidate-pool-ui`
- Files reviewed:
  - `frontend/src/pages/StrategyLab.tsx`
  - `frontend/src/pages/__tests__/StrategyLab.test.tsx`
  - `frontend/src/lib/api.ts`
  - `frontend/src/router.tsx`
  - `scripts/acceptance-pr-28`
  - `.github/PR_28_ACCEPTANCE.md`

## Review Summary

```text
Decision: approve
```

## Blocker

- None

## Important

- None

## Follow-up

- Split a dedicated `/backtest-results` page from the strategy-lab run table once users need deeper per-run drilldown from the A-share shell.

## Required Checks

- [x] The PR stays inside the current local Git project.
- [x] The new UI is Chinese.
- [x] The PR does not introduce `OPENAI_API_KEY`.
- [x] The PR does not add JoinQuant login, browser automation, remote submission, approval, live authorization, runner start, broker actions, or live trading.
- [x] Targeted PR-28 acceptance passed.
- [x] Previous PR acceptance passed.
- [x] Backend compile check passed.
- [x] Frontend full test suite passed.
- [x] Frontend build passed.
- [x] Automated smoke test passed.

## Review Checklist

| Area | Result | Evidence |
| --- | --- | --- |
| Scope control | Pass | PR-28 adds a single strategy-lab page, route wiring, typed API client methods, and targeted tests |
| UI language | Pass | Page title, controls, sections, validation errors, and guardrail copy are Chinese |
| API wiring | Pass | Frontend calls PR-10/11/12 template, spec, batch backtest, run list, and ranking routes through typed contracts |
| Research boundary | Pass | UI only generates auditable specs, runs local backtests, and displays rankings; it does not approve, export, or trade |
| Failure handling | Pass | Local invalid input and Chinese backend prerequisite errors render directly in the page |
| Automated acceptance | Pass | `scripts/acceptance-pr-28` covers render, templates, specs, batch backtests, rankings, validation, navigation, and guardrails |

## Verification Evidence

```text
bash scripts/acceptance-pr-28
13 tests passed; PR-28 acceptance passed.

bash scripts/acceptance-pr-27
13 tests passed; PR-27 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run test:run
29 test files passed; 248 tests passed.

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
