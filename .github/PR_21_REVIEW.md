# PR-21 Code Review

## Scope

- PR: PR-21
- Branch: `codex/pr-21-simulation-readiness-ui`
- Base: `codex/pr-20-simulation-readiness-report`
- Files reviewed:
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/JoinQuantExport.tsx`
  - `frontend/src/pages/__tests__/JoinQuantExport.test.tsx`
  - `scripts/acceptance-pr-21`
  - `.github/PR_21_ACCEPTANCE.md`

## Review Summary

```text
Decision: approve
```

## Blocker

- None

## Important

- None

## Follow-up

- After importing real JoinQuant simulation reports, tune the default observation window and thresholds from actual user workflow data.

## Required Checks

- [x] The PR stays inside the current local Git project.
- [x] The PR keeps the UI in Chinese.
- [x] The PR does not introduce `OPENAI_API_KEY`.
- [x] The PR does not add JoinQuant login, browser automation, remote submission, live trading, or broker actions.
- [x] Frontend targeted acceptance passed.
- [x] Previous PR acceptance passed.
- [x] Backend compile check passed.
- [x] Frontend full test suite passed.
- [x] Frontend build passed.
- [x] Automated smoke test passed.

## Review Checklist

| Area | Result | Evidence |
| --- | --- | --- |
| Scope control | Pass | PR-21 adds frontend API typing and a readiness panel on the existing JoinQuant page only |
| API-key guardrail | Pass | No `OPENAI_API_KEY`, paid LLM API client, or model-call path is introduced |
| Trading guardrail | Pass | UI only reads local readiness data and does not log in to JoinQuant, submit remotely, call brokers, or enable live trading |
| UI language | Pass | New panel labels, statuses, recommendations, validation errors, and safety copy are Chinese |
| Readiness UX | Pass | Users can set portfolio, observation window, minimum batches, tolerance, and view score, recommendation, checks, findings, metrics, and daily summaries |
| Automated acceptance | Pass | `scripts/acceptance-pr-21` covers UI behavior, API wiring, invalid parameter handling, and guardrails |

## Verification Evidence

```text
bash scripts/acceptance-pr-21
12 tests passed; PR-21 acceptance passed.

bash scripts/acceptance-pr-20
16 tests passed; PR-20 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run test:run
25 test files passed; 225 tests passed.

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
