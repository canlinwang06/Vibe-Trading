# PR-12 Acceptance Cases

## Scope

- PR: PR-12
- Branch: `codex/pr-12-backtest-ranking`
- Feature area: A-share strategy-lab backtest ranking and strategy scoring

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-12
```

Expected result:

```text
PR-12 acceptance passed.
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
| PR-12-001 | Rank completed backtests | Seed strategy specs, seed local candidates/market data, run batch backtest, then list rankings | Ranked rows include `rank`, `strategy_score`, `risk_score`, recommendation, and score components | `bash scripts/acceptance-pr-12` |
| PR-12-002 | Score uses multi-factor model | Inspect scoring model returned by service/API | Model includes return, stability, drawdown, risk-adjusted return, correlation control, turnover, and sample stability weights | `bash scripts/acceptance-pr-12` |
| PR-12-003 | Ranking order is deterministic | Generate multiple completed runs | Results sort by descending `strategy_score`, then lower risk, then return and strategy id | `bash scripts/acceptance-pr-12` |
| PR-12-004 | Strategy-type filter works | Query rankings for one strategy type | Returned rows all match the requested `strategy_type` and ranks are recalculated | `bash scripts/acceptance-pr-12` |
| PR-12-005 | API route is mounted | Inspect FastAPI route table | `/api/strategy-lab/backtest-rankings` exists | `bash scripts/acceptance-pr-12` |
| PR-12-006 | Failure is readable in Chinese | Query rankings before any completed backtest exists | API returns a Chinese validation error | `bash scripts/acceptance-pr-12` |
| PR-12-007 | Cost and trading guardrails are preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY`, LLM API call, execution signal, broker call, or live trade is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-12
9 tests passed; PR-12 acceptance passed.

bash scripts/acceptance-pr-11
9 tests passed; PR-11 acceptance passed.

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
