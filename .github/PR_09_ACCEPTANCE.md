# PR-09 Acceptance Cases

## Scope

- PR: PR-09
- Branch: `codex/pr-09-candidate-pool`
- Feature area: A-share candidate-pool generation and manual review controls

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-09
```

Expected result:

```text
PR-09 acceptance passed.
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
| PR-09-001 | Build candidate pool from sector radar | Collect, extract, map, score sectors, then build candidates | `candidate_pool` receives system candidates from `event_stock_map` and `sector_scores` | `bash scripts/acceptance-pr-09` |
| PR-09-002 | Candidate fields support review | Query candidate pool | Rows include code, name, theme, sector, source, event heat, sector heat, stock score, risk flag, reason, and included status | `bash scripts/acceptance-pr-09` |
| PR-09-003 | User can manually add stock | Call `/api/candidate-pool/user-add` | A `user_added` row is created without creating a trade signal | `bash scripts/acceptance-pr-09` |
| PR-09-004 | User can exclude stock | Call `/api/candidate-pool/exclude` | `included` becomes false and the reason is saved | `bash scripts/acceptance-pr-09` |
| PR-09-005 | User can include stock again | Call `/api/candidate-pool/include` | `included` becomes true and the reason is saved | `bash scripts/acceptance-pr-09` |
| PR-09-006 | Candidate API routes are mounted | Inspect FastAPI route table | List, build, user-add, include, and exclude endpoints exist | `bash scripts/acceptance-pr-09` |
| PR-09-007 | Failure is readable in Chinese | Build candidates before sector scoring | API returns a Chinese validation error | `bash scripts/acceptance-pr-09` |
| PR-09-008 | Cost and trading guardrails are preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY`, LLM API call, order, or execution signal is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-09
10 tests passed; PR-09 acceptance passed.

bash scripts/acceptance-pr-08
9 tests passed; PR-08 acceptance passed.

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
