# PR-33 Code Review

## Scope

- PR: PR-33
- Branch: `codex/pr-33-signal-file-preview`
- Base: `codex/pr-32-joinquant-copy-review`
- Files reviewed:
  - `frontend/src/pages/JoinQuantExport.tsx`
  - `frontend/src/pages/__tests__/JoinQuantExport.test.tsx`
  - `scripts/acceptance-pr-33`
  - `.github/PR_33_ACCEPTANCE.md`

## Review Summary

```text
Decision: approve
```

## Blocker

- None

## Important

- None

## Follow-up

- Add a compact package manifest export if future PRs need one-click archive download for all generated files.

## Required Checks

- [x] The PR stays inside the current local Git project.
- [x] The new UI remains Chinese.
- [x] The PR does not introduce `OPENAI_API_KEY`.
- [x] The PR does not add JoinQuant login, browser automation, external JoinQuant URL, remote submission, live authorization, runner start, broker actions, or live trading.
- [x] Targeted PR-33 acceptance passed.
- [x] Previous PR acceptance passed.
- [x] Backend compile check passed.
- [x] Frontend full test suite passed.
- [x] Frontend build passed.
- [x] Automated smoke test passed.

## Review Checklist

| Area | Result | Evidence |
| --- | --- | --- |
| Scope control | Pass | PR-33 only adds JSON/CSV preview and download around existing JoinQuant copy package files |
| UI language | Pass | Signal preview, JSON/CSV labels, local-file guardrail, and download actions are Chinese |
| API wiring | Pass | Existing copy-package response is reused; no new backend or external API integration is added |
| Research boundary | Pass | Downloads are local file downloads and do not connect to JoinQuant, approve, submit, or trade |
| Failure handling | Pass | Existing blocked preflight, clipboard fallback, and report flows remain covered |
| Automated acceptance | Pass | `scripts/acceptance-pr-33` covers signal previews, JSON/CSV downloads, copy-review regression, and guardrails |

## Verification Evidence

```text
bash scripts/acceptance-pr-33
19 tests passed; PR-33 acceptance passed.

bash scripts/acceptance-pr-32
18 tests passed; PR-32 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run test:run
32 test files passed; 265 tests passed.

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
