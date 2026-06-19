# PR-31 Acceptance Cases

## Scope

- PR: PR-31
- Branch: `codex/pr-31-trade-plan-ui`
- Feature area: Trade-plan Chinese UI

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-31
```

Expected result:

```text
PR-31 acceptance passed.
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
| PR-31-001 | Render Chinese trade-plan page | Open `/trade-plan` | Page shows `交易计划`, Chinese query controls, and `草稿审阅 / 不审批不下单` guardrail | `bash scripts/acceptance-pr-31` |
| PR-31-002 | Refresh draft trade plan | Click `刷新交易计划` | Frontend calls `/api/portfolio-risk/trade-plan` and displays target exposure, strategy exposure, cash weight, target positions, and risk limits | `bash scripts/acceptance-pr-31` |
| PR-31-003 | Review target positions | Load a mocked plan | Page displays ticker, ticker name, theme, sector, target weight, current weight, delta, action, strategy source, reason, and risk warning | `bash scripts/acceptance-pr-31` |
| PR-31-004 | Review strategy sources | Load a mocked plan | Page displays strategy allocations used to build the trade plan | `bash scripts/acceptance-pr-31` |
| PR-31-005 | Local validation and API errors | Enter invalid risk limits or mock backend prerequisite errors | UI displays readable Chinese errors without calling approval or live trading surfaces | `bash scripts/acceptance-pr-31` |
| PR-31-006 | Navigation and route wiring | Inspect router/navigation | `/trade-plan` uses the real TradePlan page and keeps Chinese A-share navigation | `bash scripts/acceptance-pr-31` |
| PR-31-007 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, JoinQuant automation, approval, draft signal generation, broker action, live runner, or live authorization is introduced | `bash scripts/acceptance-pr-31` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-31
11 tests passed; PR-31 acceptance passed.
```

Full verification evidence is recorded in `PR_31_REVIEW.md`.
