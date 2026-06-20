# PR-29 Acceptance Cases

## Scope

- PR: PR-29
- Branch: `codex/pr-29-backtest-results-ui`
- Feature area: Backtest-results Chinese UI

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-29
```

Expected result:

```text
PR-29 acceptance passed.
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
| PR-29-001 | Render Chinese backtest-results page | Open `/backtest-results` | Page shows `回测结果`, Chinese filters, and `只读验收页` guardrail | `bash scripts/acceptance-pr-29` |
| PR-29-002 | Refresh backtest runs | Click `刷新回测结果` | Frontend calls `/api/strategy-lab/backtest-runs` and displays return, excess return, drawdown, Sharpe, win rate, and trade count | `bash scripts/acceptance-pr-29` |
| PR-29-003 | Refresh strategy rankings | Click `刷新策略排名` | Frontend calls `/api/strategy-lab/backtest-rankings` and displays score, risk, recommendation, and reason | `bash scripts/acceptance-pr-29` |
| PR-29-004 | Local validation and API errors | Enter invalid limits or mock backend prerequisite errors | UI displays readable Chinese errors without trading side effects | `bash scripts/acceptance-pr-29` |
| PR-29-005 | Navigation and route wiring | Inspect router/navigation | `/backtest-results` uses the real BacktestResults page and keeps Chinese A-share navigation | `bash scripts/acceptance-pr-29` |
| PR-29-006 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, JoinQuant automation, approval, broker action, live runner, or live authorization is introduced | `bash scripts/acceptance-pr-29` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-29
11 tests passed; PR-29 acceptance passed.
```

Full verification evidence is recorded in `PR_29_REVIEW.md`.
