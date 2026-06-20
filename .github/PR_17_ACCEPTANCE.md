# PR-17 Acceptance Cases

## Scope

- PR: PR-17
- Branch: `codex/pr-17-joinquant-copy-ui`
- Feature area: JoinQuant copy UI, clipboard action, download fallback, and local `/api` proxy

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-17
```

Expected result:

```text
PR-17 acceptance passed.
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
| PR-17-001 | Render Chinese JoinQuant copy page | Open `/joinquant-export` | Page shows Chinese copy workspace, approved-signal guard, and no-login/no-order safety boundary | `bash scripts/acceptance-pr-17` |
| PR-17-002 | Run preflight before export | Click `预检查` | Frontend calls `/api/joinquant/export/preflight` with `require_approved: true` | `bash scripts/acceptance-pr-17` |
| PR-17-003 | Block draft or invalid signals | Mock blocked preflight response | UI shows blocked state and validation error; copy package is not displayed | `bash scripts/acceptance-pr-17` |
| PR-17-004 | Generate copy package | Click `生成复制包` after passing preflight | UI shows strategy ID, signal date, target count, exposure, and package files | `bash scripts/acceptance-pr-17` |
| PR-17-005 | Copy strategy code | Click `复制策略代码` after package generation | `strategy.py` content is written to clipboard and copy timestamp is shown | `bash scripts/acceptance-pr-17` |
| PR-17-006 | Download fallback | Simulate clipboard failure and click `下载 strategy.py` | UI keeps the fallback available and creates a local file download | `bash scripts/acceptance-pr-17` |
| PR-17-007 | Clear stale package | Generate package, then edit export parameters | Old package disappears and copy action is disabled until regeneration | `bash scripts/acceptance-pr-17` |
| PR-17-008 | Ignore stale async response | Start package generation, change parameters before response returns | Old response is ignored and no copy-package request is made | `bash scripts/acceptance-pr-17` |
| PR-17-009 | Local dev proxy | Inspect Vite config | `/api` is proxied to the local backend for VS Code dev runs | `bash scripts/acceptance-pr-17` |
| PR-17-010 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, JoinQuant login automation, hardcoded JoinQuant URL, or live order action is introduced | `bash scripts/acceptance-pr-17` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-17
7 tests passed; PR-17 acceptance passed.
```

Full verification evidence is recorded in `PR_17_REVIEW.md`.
