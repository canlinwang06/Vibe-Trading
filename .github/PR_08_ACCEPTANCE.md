# PR-08 Acceptance Cases

## Scope

- PR: PR-08
- Branch: `codex/pr-08-sector-scoring`
- Feature area: Event-driven A-share sector heat scoring

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-08
```

Expected result:

```text
PR-08 acceptance passed.
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
| PR-08-001 | Sector score table exists | Initialize local A-share store | `sector_scores` table is created with heat, confirmation, breadth, flow, persistence, risk, and stage columns | `bash scripts/acceptance-pr-08` |
| PR-08-002 | Event heat feeds sector score | Collect, extract, map, then score an AI event | AI算力 receives positive `event_heat` and a ranked `sector_heat_score` | `bash scripts/acceptance-pr-08` |
| PR-08-003 | Market data improves confirmation | Seed local `sector_daily` rows before scoring | `market_confirm` is above neutral when sector returns, breadth, and volume are supportive | `bash scripts/acceptance-pr-08` |
| PR-08-004 | Cycle stage is produced | Score mapped sectors | Each scored sector returns one of cold, warming, confirmed, accelerating, climax, or fading | `bash scripts/acceptance-pr-08` |
| PR-08-005 | Sector score APIs are mounted | Inspect FastAPI route table | Run and list routes for `/api/event-radar/sector-scores` exist | `bash scripts/acceptance-pr-08` |
| PR-08-006 | Failure is readable in Chinese | Run sector scoring before event mapping | API returns a Chinese validation error | `bash scripts/acceptance-pr-08` |
| PR-08-007 | Cost guardrail is preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY` or LLM API call is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-08
9 tests passed; PR-08 acceptance passed.

bash scripts/acceptance-pr-07
10 tests passed; PR-07 acceptance passed.

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
