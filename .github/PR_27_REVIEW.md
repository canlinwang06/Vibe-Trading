# PR-27 Code Review

## Scope

- PR: PR-27
- Branch: `codex/pr-27-candidate-pool-ui`
- Base: `codex/pr-26-daily-workflow-event-reactions`
- Files reviewed:
  - `frontend/src/pages/CandidatePool.tsx`
  - `frontend/src/pages/__tests__/CandidatePool.test.tsx`
  - `frontend/src/lib/api.ts`
  - `frontend/src/router.tsx`
  - `scripts/acceptance-pr-27`
  - `.github/PR_27_ACCEPTANCE.md`

## Review Summary

```text
Decision: approve
```

## Blocker

- None

## Important

- None

## Follow-up

- Add a compact link from Daily Workflow results to `/candidate-pool` after workflow run history is introduced.

## Required Checks

- [x] The PR stays inside the current local Git project.
- [x] The new UI is Chinese.
- [x] The PR does not introduce `OPENAI_API_KEY`.
- [x] The PR does not add JoinQuant login, browser automation, remote submission, approval, live authorization, runner start, broker actions, or live trading.
- [x] Targeted PR-27 acceptance passed.
- [x] Previous PR acceptance passed.
- [x] Backend compile check passed.
- [x] Frontend full test suite passed.
- [x] Frontend build passed.
- [x] Automated smoke test passed.

## Review Checklist

| Area | Result | Evidence |
| --- | --- | --- |
| Scope control | Pass | PR-27 adds a single candidate-pool page, route wiring, typed API client methods, and targeted tests |
| UI language | Pass | Page title, filters, actions, status badges, validation errors, and review copy are Chinese |
| API wiring | Pass | Frontend calls PR-09 candidate-pool list/build/user-add/include/exclude routes through typed contracts |
| Human control | Pass | UI only reviews candidate inclusion; it does not generate draft signals, approve plans, export to JoinQuant, or start live actions |
| Failure handling | Pass | Local invalid input and Chinese backend prerequisite errors render directly in the page |
| Automated acceptance | Pass | `scripts/acceptance-pr-27` covers render, list, build, manual add, include/exclude, validation, navigation, and guardrails |

## Verification Evidence

```text
bash scripts/acceptance-pr-27
13 tests passed; PR-27 acceptance passed.

bash scripts/acceptance-pr-26
11 backend tests passed; DailyWorkflow UI tests passed; PR-26 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run test:run
28 test files passed; 241 tests passed.

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
