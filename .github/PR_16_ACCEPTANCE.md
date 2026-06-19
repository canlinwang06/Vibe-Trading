# PR-16 Acceptance Cases

## Scope

- PR: PR-16
- Branch: `codex/pr-16-joinquant-copy-package`
- Feature area: JoinQuant strategy-code template and copy-package skeleton

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-16
```

Expected result:

```text
PR-16 acceptance passed.
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
| PR-16-001 | Export complete strategy code | Seed approved signals, then export strategy code | Code includes generated metadata, `initialize`, `before_trading_start`, `handle_data`, ticker mapping, risk gate, suspension/limit checks, and embedded signals | `bash scripts/acceptance-pr-16` |
| PR-16-002 | Export copy package | Export copy package for approved signals | Package includes `strategy.py`, `signals.json`, `signals.csv`, and `README.md` | `bash scripts/acceptance-pr-16` |
| PR-16-003 | Clipboard fallback content | Export copy package | `clipboard_text` equals complete `strategy.py` content for manual copy | `bash scripts/acceptance-pr-16` |
| PR-16-004 | Block draft signals | Attempt strategy-code export from draft signals | Export is blocked by preflight | `bash scripts/acceptance-pr-16` |
| PR-16-005 | API routes are mounted | Inspect FastAPI route table | Strategy-code and copy-package endpoints exist | `bash scripts/acceptance-pr-16` |
| PR-16-006 | Cost and trading guardrails are preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY`, LLM API call, JoinQuant login, browser automation, broker call, or live trade is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-16
9 tests passed; PR-16 acceptance passed.

bash scripts/acceptance-pr-15
17 tests passed; PR-15 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run test:run
213 tests passed.

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
