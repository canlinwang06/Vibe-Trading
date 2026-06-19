# PR-11 Acceptance Cases

## Scope

- PR: PR-11
- Branch: `codex/pr-11-backtest-factory`
- Feature area: A-share strategy-lab batch backtest factory

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-11
```

Expected result:

```text
PR-11 acceptance passed.
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
| PR-11-001 | Batch backtest reads local inputs | Seed `candidate_pool`, `strategy_specs`, and `market_daily` | Backtest factory reads local research tables without external API calls | `bash scripts/acceptance-pr-11` |
| PR-11-002 | Backtest run rows are written | Run `/api/strategy-lab/backtest-batch` | `backtest_runs` receives completed runs with return, drawdown, Sharpe, turnover, and trade count | `bash scripts/acceptance-pr-11` |
| PR-11-003 | Artifacts are saved | Run a batch backtest | Each run writes `run.json` with strategy, universe, metrics, and A-share assumptions | `bash scripts/acceptance-pr-11` |
| PR-11-004 | Result APIs are mounted | Inspect FastAPI route table | Batch, list, and detail endpoints exist | `bash scripts/acceptance-pr-11` |
| PR-11-005 | Detail query works | Fetch `/api/strategy-lab/backtest-runs/{run_id}` | API returns the selected run | `bash scripts/acceptance-pr-11` |
| PR-11-006 | Failure is readable in Chinese | Run backtest before candidate pool exists | API returns a Chinese validation error | `bash scripts/acceptance-pr-11` |
| PR-11-007 | Cost and trading guardrails are preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY`, LLM API call, execution signal, broker call, or live trade is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-11
9 tests passed; PR-11 acceptance passed.

bash scripts/acceptance-pr-10
10 tests passed; PR-10 acceptance passed.

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
