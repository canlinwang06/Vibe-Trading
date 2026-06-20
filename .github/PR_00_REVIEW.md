# PR-00 Review

## Scope

- PR: PR-00
- Branch: `codex/pr-00-baseline`
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

- PR-01 should decide whether the repo-level `AGENTS.md` stays local-only or becomes a tracked project convention file.
- PR-01 should add targeted tests for A-share-only market policy once that feature exists.

## Required Checks

- [x] The PR stays inside the current local Git project.
- [x] The PR preserves A-share-only guardrails where applicable.
- [x] The PR does not introduce `OPENAI_API_KEY`.
- [x] The PR does not add live trading or broker auto-submit behavior.
- [x] Backend compile check passed.
- [x] Frontend build passed.
- [x] Automated smoke test passed.
- [x] Targeted acceptance tests for this PR passed.

## Notes

This PR only establishes local development, review, and acceptance gates. It does not change trading, research, data, strategy, or JoinQuant business behavior.
