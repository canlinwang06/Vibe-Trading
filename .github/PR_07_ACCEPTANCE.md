# PR-07 Acceptance Cases

## Scope

- PR: PR-07
- Branch: `codex/pr-07-event-theme-mapping`
- Feature area: Event-to-theme, sector, and stock mapping foundation

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-07
```

Expected result:

```text
PR-07 acceptance passed.
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
| PR-07-001 | Mapping tables exist | Initialize local A-share store | `event_sector_map` and `event_stock_map` are created | `bash scripts/acceptance-pr-07` |
| PR-07-002 | Default theme map is seeded | Query `/api/event-radar/theme-map` or service list | AI算力, 人形机器人, 半导体, 新能源, and 文娱消费 seed rows exist | `bash scripts/acceptance-pr-07` |
| PR-07-003 | Sectors and members are seeded | Initialize theme map | `sectors` and `sector_members` receive custom theme rows and A-share tickers | `bash scripts/acceptance-pr-07` |
| PR-07-004 | Event maps to sector | Collect, extract, then map an AI/robotics event | `event_sector_map` receives theme, sector, relevance, and direction | `bash scripts/acceptance-pr-07` |
| PR-07-005 | Event maps to stocks | Collect, extract, then map an AI/robotics event | `event_stock_map` receives A-share tickers and mapping reasons | `bash scripts/acceptance-pr-07` |
| PR-07-006 | Mapping API routes are mounted | Inspect FastAPI route table | Theme map, map run, sector mappings, and stock mappings endpoints exist | `bash scripts/acceptance-pr-07` |
| PR-07-007 | Failure is readable in Chinese | Run mapping before extraction | API returns a Chinese validation error | `bash scripts/acceptance-pr-07` |
| PR-07-008 | Cost guardrail is preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY` or LLM API call is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-07
10 tests passed; PR-07 acceptance passed.

bash scripts/acceptance-pr-06
6 tests passed; PR-06 acceptance passed.

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
