# PR-02 Review

## Scope

- PR: PR-02
- Branch: `codex/pr-02-cn-ashare-shell`
- Base: `codex/pr-01-ashare-safety-boundary`
- Reviewer: Codex
- Date: 2026-06-19

## Review Summary

```text
Decision: approve
Pre-Landing Review: No unresolved issues found.
```

## Scope Check

```text
Scope Check: CLEAN
Intent: Build the Chinese A-share product shell and navigation for PR-02.
Delivered: Added A-share navigation, Chinese dashboard copy, placeholder pages, route wiring, settings copy, and automated PR-02 acceptance checks.
```

## Auto-Fixed During Review

- `frontend/src/components/layout/Layout.tsx`: The language toggle showed `English` in the default Chinese shell. It now shows `切换语言`, and the layout test guards this behavior.

## Blocker

- None

## Important

- None

## Follow-up

- PR-03 should replace the current placeholder data-source page with the local data warehouse initialization flow.
- PR-14 should define the exact JoinQuant copy/export format and add clipboard-level automated tests.

## Review Notes

- The sidebar now exposes only A-share product routes while preserving legacy routes for direct-link compatibility.
- Placeholder pages state current status and safety boundaries, and they do not show mock live data or executable trading behavior.
- Product-shell copy and locale files were scanned for legacy crypto, US equity, options, futures, forex, HK equity, and direct-brokerage wording.
- The review checklist was read from the installed gstack skill path because the repository does not vendor `.agents/skills/gstack/review/checklist.md`.

## Required Checks

- [x] Default product shell is Chinese.
- [x] Left navigation contains only A-share product entries.
- [x] Legacy generic trading routes are hidden from the sidebar.
- [x] Homepage does not show non-A-share examples.
- [x] Placeholder pages are clear and do not falsely enable unfinished features.
- [x] Visible shell controls remain Chinese by default.
- [x] PR-02 targeted acceptance passed.
- [x] Full frontend test suite passed.
- [x] Backend compile check passed.
- [x] Frontend production build passed.
- [x] Repository smoke test passed.

## Evidence

```text
bash scripts/acceptance-pr-02
11 tests passed; PR-02 acceptance passed.

npm --prefix frontend run test:run
213 tests passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
