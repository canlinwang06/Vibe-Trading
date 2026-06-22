# PR-14 Acceptance Cases

## Scope

- PR: PR-14
- Branch: `codex/pr-14-draft-execution-signals`
- Feature area: A-share draft execution signals and simulation-only approval boundary

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-14
```

Expected result:

```text
PR-14 acceptance passed.
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
| PR-14-001 | Persist draft execution signals | Allocate a portfolio, then generate signals | `execution_signals` receives draft rows with target weights, action, reasons, risk notes, and validity date | `bash scripts/acceptance-pr-14` |
| PR-14-002 | Query generated signals | Call `/api/portfolio-risk/signals` after generation | API returns the draft signals and count | `bash scripts/acceptance-pr-14` |
| PR-14-003 | Require human risk confirmation | Call approve-plan without confirmation | API returns a Chinese validation error and leaves signals as draft | `bash scripts/acceptance-pr-14` |
| PR-14-004 | Approve only for simulation | Call approve-plan with `confirm_risk=true` and `simulation_only=true` | Signals become `approved`, `approved_at` is set, export remains disabled, live trading remains false | `bash scripts/acceptance-pr-14` |
| PR-14-005 | Reject live approval request | Call approve-plan with `simulation_only=false` | API returns a Chinese validation error | `bash scripts/acceptance-pr-14` |
| PR-14-006 | Protect approved signals | Try to regenerate signals for the same portfolio/date after approval | Service refuses to overwrite approved/exported/executed rows | `bash scripts/acceptance-pr-14` |
| PR-14-007 | API routes are mounted | Inspect FastAPI route table | Generate-signals, signals, and approve-plan endpoints exist | `bash scripts/acceptance-pr-14` |
| PR-14-008 | Cost and trading guardrails are preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY`, LLM API call, broker call, JoinQuant export, or live trade is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-14
8 tests passed; PR-14 acceptance passed.

bash scripts/acceptance-pr-13
13 tests passed; PR-13 acceptance passed.

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
