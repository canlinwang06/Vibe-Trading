# PR-35 Code Review

## Scope

- PR: PR-35
- Branch: `codex/pr-35-data-sources-ui`
- Base: `codex/pr-34-copy-package-download`
- Files reviewed:
  - `frontend/src/pages/DataSources.tsx`
  - `frontend/src/pages/__tests__/DataSources.test.tsx`
  - `frontend/src/router.tsx`
  - `scripts/acceptance-pr-35`
  - `.github/PR_35_ACCEPTANCE.md`

## Review Summary

```text
Decision: approve
```

## Blocker

- None

## Important

- None identified before verification.

## Follow-up

- Consider a later data-source diagnostics PR if the backend exposes per-source health checks beyond the current settings endpoint.

## Required Checks

- [x] The PR stays inside the current local Git project.
- [x] The new UI remains Chinese.
- [x] The PR does not introduce model API key requirements.
- [x] The PR does not add JoinQuant login, browser automation, external JoinQuant URL, remote submission, live authorization, runner start, broker actions, or live trading.
- [x] Targeted PR-35 acceptance passed.
- [x] Previous PR acceptance passed.
- [x] Backend compile check passed.
- [x] Frontend full test suite passed.
- [x] Frontend build passed.
- [x] Automated smoke test passed.

## Review Checklist

| Area | Result | Evidence |
| --- | --- | --- |
| Scope control | Pass | PR-35 only replaces the data-source placeholder with a real local settings UI |
| UI language | Pass | Page title, credential form, status cards, and safety boundary are Chinese |
| API wiring | Pass | `getDataSourceSettings` and `updateDataSourceSettings` are reused |
| Credential safety | Pass | Saved token plaintext is never rendered; clearing requires an explicit checkbox |
| Cost boundary | Pass | Page keeps free/local data priority and avoids new model API key requirements |
| Trading boundary | Pass | Page remains research/simulation only |
| Automated acceptance | Pass | `scripts/acceptance-pr-35` passed |

## Verification Evidence

```text
bash scripts/acceptance-pr-35
11 tests passed; PR-35 acceptance passed.

bash scripts/acceptance-pr-34
20 tests passed; PR-34 acceptance passed.

.venv/bin/python -m compileall -q agent
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
