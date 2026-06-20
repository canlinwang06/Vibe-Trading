# PR-18 Acceptance Cases

## Scope

- PR: PR-18
- Branch: `codex/pr-18-joinquant-execution-import`
- Feature area: JoinQuant execution-report import and reconciliation summary

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-18
```

Expected result:

```text
PR-18 acceptance passed.
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
| PR-18-001 | Reverse JoinQuant ticker mapping | Import reports with `600519.XSHG` and `300750.XSHE` | Reports are stored as local `600519.SH` and `300750.SZ` | `bash scripts/acceptance-pr-18` |
| PR-18-002 | Import execution reports | Seed approved signals, then import JoinQuant report rows | Rows persist in `jq_execution_reports` with raw report payloads | `bash scripts/acceptance-pr-18` |
| PR-18-003 | Reconcile execution summary | Import filled, held, and rejected rows | Summary reports matched signals, failed count, weight deviation, and action-required state | `bash scripts/acceptance-pr-18` |
| PR-18-004 | Replace same trade-date reports | Import rows, then re-import with `replace=true` | Old rows for the same portfolio/signal/trade date are removed before new rows are stored | `bash scripts/acceptance-pr-18` |
| PR-18-005 | Reject unsupported JoinQuant ticker | Import `830000.XBSE` | Import is blocked with a readable mapping error | `bash scripts/acceptance-pr-18` |
| PR-18-006 | Reject mixed batches | Import rows with different trade dates in one request | Import is blocked so the response summary cannot mix unrelated batches | `bash scripts/acceptance-pr-18` |
| PR-18-007 | API round trip | Call import, list, and summary endpoints | API returns persisted reports and reconciliation summary | `bash scripts/acceptance-pr-18` |
| PR-18-008 | Route registration | Inspect FastAPI route table | Execution-report import/list/summary routes are mounted | `bash scripts/acceptance-pr-18` |
| PR-18-009 | Cost and trading guardrails | Inspect JoinQuant adapter and routes | No `OPENAI_API_KEY`, browser automation, or JoinQuant remote submission is introduced | `bash scripts/acceptance-pr-18` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-18
13 tests passed; PR-18 acceptance passed.
```

Full verification evidence is recorded in `PR_18_REVIEW.md`.
