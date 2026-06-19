# PR-23 Acceptance Cases

## Scope

- PR: PR-23
- Branch: `codex/pr-23-daily-workflow-ui`
- Feature area: Daily workflow Chinese UI

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-23
```

Expected result:

```text
PR-23 acceptance passed.
```

## Baseline Smoke Command

Command:

```bash
bash scripts/smoke
```

Expected result:

```text
PR smoke test passed.
```

## Targeted Acceptance Cases

| Case ID | Scenario | Steps | Expected Result | Automated Command |
| --- | --- | --- | --- | --- |
| PR-23-001 | Render Chinese workflow page | Open `/daily-workflow` | Page shows `每日研究工作流`, AI 产业链 default task, Chinese controls, and safety boundary | `bash scripts/acceptance-pr-23` |
| PR-23-002 | Dry-run workflow | Click `试运行` | UI calls `/api/daily-workflow/run` with `dry_run=true` and renders planned steps | `bash scripts/acceptance-pr-23` |
| PR-23-003 | Run workflow | Click `运行工作流` with default selected steps | UI calls the backend and displays completed steps plus draft-signal evidence | `bash scripts/acceptance-pr-23` |
| PR-23-004 | Blocked step feedback | Backend returns `blocked` | UI shows the blocked step, Chinese message, and progress state | `bash scripts/acceptance-pr-23` |
| PR-23-005 | Empty step validation | Clear all steps and click run | UI blocks submission locally and does not call the backend | `bash scripts/acceptance-pr-23` |
| PR-23-006 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, browser automation, JoinQuant remote submit flow, live authorization, runner start, approval, or broker action is introduced | `bash scripts/acceptance-pr-23` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-23
8 tests passed; PR-23 acceptance passed.
```

Full verification evidence is recorded in `PR_23_REVIEW.md`.
