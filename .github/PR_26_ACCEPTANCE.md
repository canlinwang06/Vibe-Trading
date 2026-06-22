# PR-26 Acceptance Cases

## Scope

- PR: PR-26
- Branch: `codex/pr-26-daily-workflow-event-reactions`
- Feature area: Daily workflow event reaction integration

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-26
```

Expected result:

```text
PR-26 acceptance passed.
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
| PR-26-001 | Workflow step registration | Inspect daily workflow service | `calculate_event_reactions` is an allowed step and dry-run planned message is available | `bash scripts/acceptance-pr-26` |
| PR-26-002 | Full local workflow | Run the full daily workflow with local AI policy event and market data | Workflow completes, writes draft signals, and writes local `event_reactions` rows | `bash scripts/acceptance-pr-26` |
| PR-26-003 | API request contract | Inspect `/api/daily-workflow/run` request model | Event reaction windows, target types, limit, and replace flag are accepted | `bash scripts/acceptance-pr-26` |
| PR-26-004 | UI workflow step | Open `/daily-workflow` | Page exposes the Chinese `事件反应` step and sends reaction windows/target types to the backend | `bash scripts/acceptance-pr-26` |
| PR-26-005 | Regression | Run PR-24 event reaction tests | Standalone event reaction APIs still pass | `bash scripts/acceptance-pr-26` |
| PR-26-006 | Cost and trading guardrails | Inspect workflow integration | No `OPENAI_API_KEY`, browser automation, JoinQuant remote URL, approval, live-trading, or broker order path is introduced | `bash scripts/acceptance-pr-26` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-26
11 backend tests passed; DailyWorkflow UI tests passed; PR-26 acceptance passed.
```

Full verification evidence is recorded in `PR_26_REVIEW.md`.
