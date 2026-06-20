# PR-10 Acceptance Cases

## Scope

- PR: PR-10
- Branch: `codex/pr-10-strategy-templates`
- Feature area: A-share strategy template library and `strategy_specs`

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-10
```

Expected result:

```text
PR-10 acceptance passed.
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
| PR-10-001 | Eight standard templates exist | Query strategy templates | S01-S08 auditable strategy templates are returned | `bash scripts/acceptance-pr-10` |
| PR-10-002 | Template specs are seeded | Run `/api/strategy-lab/specs/seed` | 8 templates x 3 variants create 24 `strategy_specs` rows | `bash scripts/acceptance-pr-10` |
| PR-10-003 | Seeding is idempotent | Run seed twice with `replace=false` | Second run skips existing specs without duplicates | `bash scripts/acceptance-pr-10` |
| PR-10-004 | Strategy specs stay research-only | List seeded specs | Params include `execution_mode=research_only` and data inputs from candidate/sector tables | `bash scripts/acceptance-pr-10` |
| PR-10-005 | Custom spec is constrained to templates | Create a spec with a supported `strategy_type` | The row is saved to `strategy_specs` with bounded risk parameters | `bash scripts/acceptance-pr-10` |
| PR-10-006 | Unsupported random strategy is rejected | Create a spec with an unknown `strategy_type` | API returns a Chinese validation error | `bash scripts/acceptance-pr-10` |
| PR-10-007 | Strategy-lab routes are mounted | Inspect FastAPI route table | Template, seed, list, and create endpoints exist | `bash scripts/acceptance-pr-10` |
| PR-10-008 | Cost and trading guardrails are preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY`, LLM API call, backtest run, order, or execution signal is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-10
10 tests passed; PR-10 acceptance passed.

bash scripts/acceptance-pr-09
10 tests passed; PR-09 acceptance passed.

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
