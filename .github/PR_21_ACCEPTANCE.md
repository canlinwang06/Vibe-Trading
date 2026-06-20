# PR-21 Acceptance Cases

## Scope

- PR: PR-21
- Branch: `codex/pr-21-simulation-readiness-ui`
- Feature area: JoinQuant simulation-readiness Chinese UI

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-21
```

Expected result:

```text
PR-21 acceptance passed.
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
| PR-21-001 | Render Chinese readiness panel | Open `/joinquant-export` | Page shows `模拟盘准备度`, local safety copy, and `生成准备度报告` action | `bash scripts/acceptance-pr-21` |
| PR-21-002 | Generate readiness report | Set observation parameters and click `生成准备度报告` | Frontend calls readiness API and displays score, recommendation, checks, findings, metrics, and daily summaries | `bash scripts/acceptance-pr-21` |
| PR-21-003 | Reject invalid parameters | Enter invalid observation days and click generate | UI shows a Chinese validation error and does not call the backend | `bash scripts/acceptance-pr-21` |
| PR-21-004 | API wiring | Inspect frontend API client | `/api/joinquant/simulation-readiness` is wired with typed query and response contracts | `bash scripts/acceptance-pr-21` |
| PR-21-005 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, JoinQuant browser automation, hardcoded JoinQuant URL, or remote submit flow is introduced | `bash scripts/acceptance-pr-21` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-21
12 tests passed; PR-21 acceptance passed.
```

Full verification evidence is recorded in `PR_21_REVIEW.md`.
