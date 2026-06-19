# PR-28 Acceptance Cases

## Scope

- PR: PR-28
- Branch: `codex/pr-28-strategy-lab-ui`
- Feature area: Strategy-lab Chinese UI

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-28
```

Expected result:

```text
PR-28 acceptance passed.
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
| PR-28-001 | Render Chinese strategy-lab page | Open `/strategy-lab` | Page shows `策略实验室`, Chinese controls, and `研究回测，不下单` guardrail | `bash scripts/acceptance-pr-28` |
| PR-28-002 | Load strategy templates | Click `加载模板` | Frontend calls `/api/strategy-lab/templates` and renders template cards | `bash scripts/acceptance-pr-28` |
| PR-28-003 | Seed and list strategy specs | Click `生成策略规格` | Frontend calls `/api/strategy-lab/specs/seed`, then lists strategy specs | `bash scripts/acceptance-pr-28` |
| PR-28-004 | Run batch backtests | Click `运行批量回测` | Frontend calls `/api/strategy-lab/backtest-batch` and renders top backtest runs | `bash scripts/acceptance-pr-28` |
| PR-28-005 | Refresh backtest runs and rankings | Click `刷新回测` and `刷新排名` | Frontend calls backtest-run and ranking APIs and displays metrics, scores, recommendation, and reason | `bash scripts/acceptance-pr-28` |
| PR-28-006 | Local validation and API errors | Enter invalid limits or mock backend prerequisite errors | UI displays readable Chinese errors without trading side effects | `bash scripts/acceptance-pr-28` |
| PR-28-007 | Navigation and route wiring | Inspect router/navigation | `/strategy-lab` uses the real StrategyLab page and keeps Chinese A-share navigation | `bash scripts/acceptance-pr-28` |
| PR-28-008 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, JoinQuant automation, approval, broker action, live runner, or live authorization is introduced | `bash scripts/acceptance-pr-28` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-28
13 tests passed; PR-28 acceptance passed.
```

Full verification evidence is recorded in `PR_28_REVIEW.md`.
