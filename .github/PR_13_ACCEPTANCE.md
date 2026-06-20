# PR-13 Acceptance Cases

## Scope

- PR: PR-13
- Branch: `codex/pr-13-portfolio-allocation`
- Feature area: A-share portfolio-risk allocation from ranked strategy backtests

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-13
```

Expected result:

```text
PR-13 acceptance passed.
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
| PR-13-001 | Allocate ranked strategies | Seed local candidates, strategy specs, market data, backtests, then run portfolio allocation | `strategy_allocations` receives 3-5 draft strategy weights | `bash scripts/acceptance-pr-13` |
| PR-13-002 | Respect strategy caps | Allocate with single-strategy cap and strategy-type cap | No strategy exceeds 30%; no strategy type exceeds 50% | `bash scripts/acceptance-pr-13` |
| PR-13-003 | Output cash and exposure | Run allocation under normal regime | Response includes model exposure, allocated exposure, and cash weight | `bash scripts/acceptance-pr-13` |
| PR-13-004 | Apply drawdown risk-off | Allocate with -10% current drawdown | Status becomes `risk_off`, exposure is 0, cash is 100% | `bash scripts/acceptance-pr-13` |
| PR-13-005 | Produce draft target positions | Query `/api/portfolio-risk/trade-plan` after allocation | Draft target positions are generated with single-stock and sector caps | `bash scripts/acceptance-pr-13` |
| PR-13-006 | Keep execution disabled | Generate a draft trade plan | `execution_signals` remains empty; output is research-only and unapproved | `bash scripts/acceptance-pr-13` |
| PR-13-007 | API routes are mounted | Inspect FastAPI route table | Allocate, allocations, and trade-plan endpoints exist | `bash scripts/acceptance-pr-13` |
| PR-13-008 | Failure is readable in Chinese | Query trade plan before allocation | API returns a Chinese validation error | `bash scripts/acceptance-pr-13` |

## Evidence

Latest local run:

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
