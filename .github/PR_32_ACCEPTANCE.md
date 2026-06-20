# PR-32 Acceptance Cases

## Scope

- PR: PR-32
- Branch: `codex/pr-32-joinquant-copy-review`
- Feature area: JoinQuant copy-review UI

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-32
```

Expected result:

```text
PR-32 acceptance passed.
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
| PR-32-001 | Render Chinese JoinQuant copy workspace | Open `/joinquant-export` | Page shows Chinese export, copy, execution-report, and readiness sections | `bash scripts/acceptance-pr-32` |
| PR-32-002 | Generate copy package with review | Click `生成复制包` after a passing preflight | Page shows `复制前审阅`, strategy name, stock pool, signal window, target source, mapping check, syntax check, risk notice, and copy summary | `bash scripts/acceptance-pr-32` |
| PR-32-003 | Copy strategy and show latest copy time | Click `复制策略代码` | Code is written only to the local clipboard and UI displays recent copy time | `bash scripts/acceptance-pr-32` |
| PR-32-004 | Download fallback remains available | Simulate clipboard failure and click `下载 strategy.py` | UI shows readable failure and supports `Download Python Strategy` fallback | `bash scripts/acceptance-pr-32` |
| PR-32-005 | Blocked preflight stays blocked | Mock failed preflight | UI keeps validation errors visible and does not show a copy package | `bash scripts/acceptance-pr-32` |
| PR-32-006 | Navigation and route wiring | Inspect router/navigation | `/joinquant-export` uses the real JoinQuantExport page and keeps Chinese A-share navigation | `bash scripts/acceptance-pr-32` |
| PR-32-007 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, JoinQuant browser automation, external JoinQuant URL, broker action, live runner, or live authorization is introduced | `bash scripts/acceptance-pr-32` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-32
18 tests passed; PR-32 acceptance passed.
```

Full verification evidence is recorded in `PR_32_REVIEW.md`.
