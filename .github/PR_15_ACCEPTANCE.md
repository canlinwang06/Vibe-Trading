# PR-15 Acceptance Cases

## Scope

- PR: PR-15
- Branch: `codex/pr-15-joinquant-signal-export`
- Feature area: JoinQuant ticker mapping, signal preflight, and JSON/CSV export

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-15
```

Expected result:

```text
PR-15 acceptance passed.
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
| PR-15-001 | Map local A-share tickers | Map `600519.SH`, `300750.SZ`, and `000001.SH` | Codes become `600519.XSHG`, `300750.XSHE`, and `000001.XSHG` | `bash scripts/acceptance-pr-15` |
| PR-15-002 | Preflight approved signals | Seed approved local `execution_signals`, then run JoinQuant preflight | Preflight passes and reports `copy_ready=true` | `bash scripts/acceptance-pr-15` |
| PR-15-003 | Block draft signals | Seed draft signals, then run preflight/export | Export is blocked with a Chinese approved-status error | `bash scripts/acceptance-pr-15` |
| PR-15-004 | Block unsupported tickers | Seed an unsupported exchange ticker | Preflight blocks export with a mapping error | `bash scripts/acceptance-pr-15` |
| PR-15-005 | Export signals JSON | Export approved signals JSON | Payload matches the required JoinQuant signal JSON shape and contains mapped tickers | `bash scripts/acceptance-pr-15` |
| PR-15-006 | Export signals CSV | Export approved signals CSV | CSV text includes mapped tickers, source tickers, target weights, reasons, and risks | `bash scripts/acceptance-pr-15` |
| PR-15-007 | API routes are mounted | Inspect FastAPI route table | Preflight, signals-json, and signals-csv endpoints exist | `bash scripts/acceptance-pr-15` |
| PR-15-008 | Cost and trading guardrails are preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY`, LLM API call, broker call, JoinQuant login, browser automation, or live trade is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-15
14 tests passed; PR-15 acceptance passed.

bash scripts/acceptance-pr-14
8 tests passed; PR-14 acceptance passed.

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
