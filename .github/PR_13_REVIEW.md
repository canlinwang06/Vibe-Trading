# PR-13 Code Review

## Review Scope

- Branch: `codex/pr-13-portfolio-allocation`
- Base: `codex/pr-12-backtest-ranking`
- Files reviewed:
  - `agent/src/portfolio_risk/service.py`
  - `agent/src/api/portfolio_risk_routes.py`
  - `agent/api_server.py`
  - `agent/tests/test_portfolio_risk.py`
  - `scripts/acceptance-pr-13`
  - `.github/PR_13_ACCEPTANCE.md`

## Findings

No blocking issues found in the PR-13 self-review after the planned verification commands passed.

## Review Checklist

| Area | Result | Evidence |
| --- | --- | --- |
| Scope control | Pass | PR-13 writes strategy allocations and draft trade-plan output; approval/export/execution are deferred |
| API-key guardrail | Pass | No `OPENAI_API_KEY` usage, no LLM API client, no paid external call |
| Trading guardrail | Pass | No `execution_signals` writes, broker calls, live orders, or approved execution state |
| Risk constraints | Pass | Strategy cap, strategy-type cap, drawdown risk-off, stock cap, and sector cap are tested |
| Chinese UX | Pass | User-facing errors and risk-rule labels are Chinese |
| Automated acceptance | Pass | `scripts/acceptance-pr-13` covers service and API behavior |

## Verification Evidence

```text
bash scripts/acceptance-pr-13
11 tests passed; PR-13 acceptance passed.

bash scripts/acceptance-pr-12
9 tests passed; PR-12 acceptance passed.

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
