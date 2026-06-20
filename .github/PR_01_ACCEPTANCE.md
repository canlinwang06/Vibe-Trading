# PR-01 Acceptance Cases

## Scope

- PR: PR-01
- Branch: `codex/pr-01-ashare-safety-boundary`
- Feature area: A-share-only research mode and safety boundary

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-01
```

Expected result:

```text
PR-01 acceptance passed.
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
| PR-01-001 | Valid A-share symbols enter the research flow | Validate `600519.SH`, `300750.SZ`, `000001.SZ` | Symbols are accepted and normalized | `bash scripts/acceptance-pr-01` |
| PR-01-002 | US equity is rejected | Validate `AAPL.US` | Request is rejected with a `CN_A_ONLY` policy error | `bash scripts/acceptance-pr-01` |
| PR-01-003 | Crypto is rejected | Validate `BTC-USDT` | Request is rejected with a `CN_A_ONLY` policy error | `bash scripts/acceptance-pr-01` |
| PR-01-004 | HK equity is rejected | Validate `0700.HK` | Request is rejected with a `CN_A_ONLY` policy error | `bash scripts/acceptance-pr-01` |
| PR-01-005 | Backtest config is research-only | Validate an A-share daily config | Config is daily, long-only, cash-only, and `trade_plan_status=draft` | `bash scripts/acceptance-pr-01` |
| PR-01-006 | Disabled trade modes are blocked | Try crypto, options engine, futures, forex, leverage, and short flags | Each request is rejected before execution | `bash scripts/acceptance-pr-01` |
| PR-01-007 | Generated backtest code cannot bypass policy | Run the backtest tool with `BTC-USDT` | Tool returns an error before generated signal code runs | `bash scripts/acceptance-pr-01` |
| PR-01-008 | Correlation route is A-share-only | Ask for crypto correlation | Request is rejected before data fetching | `bash scripts/acceptance-pr-01` |
| PR-01-009 | Agent system prompt carries the boundary | Build the prompt section | Prompt states A-share-only, draft plans, no automatic order placement | `bash scripts/acceptance-pr-01` |
| PR-01-010 | Live enablement is blocked | Try authorize, mandate commit, resume, and runner start actions | Each action is blocked by default research mode | `bash scripts/acceptance-pr-01` |
| PR-01-011 | Homepage examples are Chinese A-share tasks | Render welcome screen | User-facing entry points show A-share research, draft plan, and JoinQuant-copy preparation | `bash scripts/acceptance-pr-01` |
| PR-01-012 | Legacy market examples are absent from entry points | Scan welcome and correlation pages | No BTC, AAPL, crypto, options, or trading connector examples remain | `bash scripts/acceptance-pr-01` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-01
PR-01 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

PYTHONPATH=agent .venv/bin/python -m pytest -q agent/tests/test_market_policy.py agent/tests/test_api_live_runtime.py::test_authorize_onramp_describes_cli_flow agent/tests/test_api_live_runtime.py::test_runner_start_success_then_idempotent agent/tests/test_engine_robustness.py::TestBacktestConfigSchema agent/tests/test_consent_commit.py::test_propose_is_readonly_and_clamps_to_ceilings
35 passed
```
