# PR-25 Acceptance Cases

## Scope

- PR: PR-25
- Branch: `codex/pr-25-event-reaction-ui`
- Feature area: Event reaction Chinese UI

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-25
```

Expected result:

```text
PR-25 acceptance passed.
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
| PR-25-001 | Render Chinese event reaction page | Open `/event-reactions` | Page shows `事件反应研究`, AI算力 default filter, read-only guardrail, and calculate/summary/detail actions | `bash scripts/acceptance-pr-25` |
| PR-25-002 | Calculate reactions | Click `计算事件反应` | Frontend calls `/api/event-reactions/calculate` with T+1/T+5/T+20/T+60 and stock/sector target types | `bash scripts/acceptance-pr-25` |
| PR-25-003 | Render summary | Click `生成摘要` | UI calls summary API and displays average return, benchmark, abnormal return, and drawdown metrics | `bash scripts/acceptance-pr-25` |
| PR-25-004 | Render details | Click `刷新明细` | UI calls list API and displays per-target reaction rows | `bash scripts/acceptance-pr-25` |
| PR-25-005 | Error handling | Backend returns a Chinese prerequisite error | UI displays the Chinese error message | `bash scripts/acceptance-pr-25` |
| PR-25-006 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, browser automation, JoinQuant remote submit flow, live authorization, runner start, approval, or broker action is introduced | `bash scripts/acceptance-pr-25` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-25
10 tests passed; PR-25 acceptance passed.
```

Full verification evidence is recorded in `PR_25_REVIEW.md`.
