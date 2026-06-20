# PR Acceptance Template

## PR

- PR:
- Branch:
- Feature area:
- Date:

## Overall Smoke Test

Command:

```bash
bash scripts/smoke
```

Expected result:

```text
PR smoke test passed.
```

## Targeted Acceptance Cases

Add cases that specifically cover this PR's changes.

| Case ID | Scenario | Steps | Expected Result | Automated Command |
| --- | --- | --- | --- | --- |
| PR-XX-001 | Replace with PR-specific scenario | Replace with steps | Replace with expected result | Replace with command |

## Manual Checks

- [ ] The page or workflow is understandable in Chinese.
- [ ] Empty, loading, success, and failure states are covered where relevant.
- [ ] No non-A-share market entry points are exposed unless explicitly in scope.
- [ ] No automatic live trading or broker submission is exposed.

## Evidence

Paste command summaries, screenshot paths, or PR links here. Do not paste secrets.
