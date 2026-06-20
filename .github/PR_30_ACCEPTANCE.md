# PR-30 Acceptance Cases

## Scope

- PR: PR-30
- Branch: `codex/pr-30-risk-portfolio-ui`
- Feature area: Risk-portfolio Chinese UI

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-30
```

Expected result:

```text
PR-30 acceptance passed.
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
| PR-30-001 | Render Chinese risk-portfolio page | Open `/risk-portfolio` | Page shows `风控组合`, Chinese controls, and `不审批 / 不下单` guardrail | `bash scripts/acceptance-pr-30` |
| PR-30-002 | Run portfolio allocation | Click `运行组合风控` | Frontend calls `/api/portfolio-risk/allocate` and displays model exposure, allocated exposure, cash weight, strategy weights, and risk rules | `bash scripts/acceptance-pr-30` |
| PR-30-003 | Refresh persisted allocations | Click `刷新策略分配` | Frontend calls `/api/portfolio-risk/allocations` and displays persisted strategy allocation rows | `bash scripts/acceptance-pr-30` |
| PR-30-004 | Generate draft trade plan | Click `生成交易计划草案` | Frontend calls `/api/portfolio-risk/trade-plan` and displays target positions as an unapproved draft | `bash scripts/acceptance-pr-30` |
| PR-30-005 | Local validation and API errors | Enter invalid top-N or mock backend prerequisite errors | UI displays readable Chinese errors without calling live trading surfaces | `bash scripts/acceptance-pr-30` |
| PR-30-006 | Navigation and route wiring | Inspect router/navigation | `/risk-portfolio` uses the real RiskPortfolio page and keeps Chinese A-share navigation | `bash scripts/acceptance-pr-30` |
| PR-30-007 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, JoinQuant automation, approval, draft signal generation, broker action, live runner, or live authorization is introduced | `bash scripts/acceptance-pr-30` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-30
12 tests passed; PR-30 acceptance passed.
```

Full verification evidence is recorded in `PR_30_REVIEW.md`.
