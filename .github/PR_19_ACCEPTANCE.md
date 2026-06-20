# PR-19 Acceptance Cases

## Scope

- PR: PR-19
- Branch: `codex/pr-19-joinquant-report-ui`
- Feature area: JoinQuant execution-report import UI and reconciliation display

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-19
```

Expected result:

```text
PR-19 acceptance passed.
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
| PR-19-001 | Render Chinese report import panel | Open `/joinquant-export` | Page shows `执行报告导入`, report batch inputs, JSON paste area, and local-only report notice | `bash scripts/acceptance-pr-19` |
| PR-19-002 | Import pasted execution reports | Paste JoinQuant-style JSON rows and click `导入报告` | Frontend calls the import API and displays imported count, summary, deviations, and recent reports | `bash scripts/acceptance-pr-19` |
| PR-19-003 | Reject invalid report JSON | Paste invalid JSON and click `导入报告` | UI shows a readable Chinese validation error and does not call the backend | `bash scripts/acceptance-pr-19` |
| PR-19-004 | Query reconciliation summary | Set portfolio/date/tolerance and click `查询复盘` | Frontend calls summary and list APIs, then shows reconciliation metrics and recent reports | `bash scripts/acceptance-pr-19` |
| PR-19-005 | API wiring | Inspect frontend API client | Import, list, and summary endpoints are wired to local `/api/joinquant/execution-reports*` routes | `bash scripts/acceptance-pr-19` |
| PR-19-006 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, JoinQuant browser automation, hardcoded JoinQuant URL, or remote submit flow is introduced | `bash scripts/acceptance-pr-19` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-19
10 tests passed; PR-19 acceptance passed.
```

Full verification evidence is recorded in `PR_19_REVIEW.md`.
