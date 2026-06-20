# PR-01 Review

## Scope

- PR: PR-01
- Branch: `codex/pr-01-ashare-safety-boundary`
- Reviewer: Codex
- Date: 2026-06-19

## Review Summary

```text
Decision: approve
```

## Blocker

- None

## Important

- None

## Follow-up

- PR-02 should continue the UI work by hiding or relabeling broader multi-market features outside the PR-01 entry points.
- PR-02 or PR-03 should define the exact JoinQuant copy format and add clipboard-level acceptance tests once that UI is implemented.

## Review Notes

- Review found that direct runner validation normalized symbols but did not preserve the default `trade_plan_status=draft` in the schema dump. This was fixed before final validation by writing all policy-normalized fields back to the model.
- Existing live-runtime and consent tests now explicitly set `CN_A_ONLY=0` because they test the legacy live infrastructure, while PR-01 adds separate default-mode tests for the product safety boundary.

## Required Checks

- [x] AAPL.US is rejected in A-share-only mode.
- [x] BTC-USDT is rejected in A-share-only mode.
- [x] 0700.HK is rejected in A-share-only mode.
- [x] 600519.SH can enter the research/backtest configuration flow.
- [x] Backtest configs default to draft trade plans.
- [x] Short, leverage, crypto, futures, options, and forex modes are blocked.
- [x] Live authorize, mandate commit, live resume, and runner start are blocked by default.
- [x] Homepage and correlation entry points use Chinese A-share examples.
- [x] PR-01 targeted acceptance passed.
- [x] Backend compile check passed.
- [x] Frontend build and smoke test passed.

## Evidence

```text
bash scripts/acceptance-pr-01
19 backend tests passed; 5 frontend tests passed; PR-01 acceptance passed.

.venv/bin/python -m compileall -q agent && bash scripts/smoke
PR smoke test passed.
```
