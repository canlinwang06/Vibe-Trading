# PR-03 Acceptance Cases

## Scope

- PR: PR-03
- Branch: `codex/pr-03-local-data-store`
- Feature area: Local DuckDB data store and PR-03 core tables

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-03
```

Expected result:

```text
PR-03 acceptance passed.
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
| PR-03-001 | A-share local store can be initialized with one command | Run `scripts/init-ashare-store --json` with a temporary `ASHARE_DATA_ROOT` | DuckDB file and Parquet sidecar directory are created | `bash scripts/acceptance-pr-03` |
| PR-03-002 | Initialization is idempotent | Run initialization twice against the same temporary root | Existing tables and rows are preserved | `bash scripts/acceptance-pr-03` |
| PR-03-003 | PR-03 core tables exist | Inspect DuckDB `information_schema.tables` | All 17 PR-03 tables exist in the expected order | `bash scripts/acceptance-pr-03` |
| PR-03-004 | Requirement fields are present | Inspect representative table columns | assets, raw_documents, events, candidate_pool, execution_signals, and jq_execution_reports expose key fields from the requirements document | `bash scripts/acceptance-pr-03` |
| PR-03-005 | Basic read/write works | Insert and query A-share asset and candidate-pool rows | Rows can be read back and default market is `CN_A` | `bash scripts/acceptance-pr-03` |
| PR-03-006 | No external data collection is triggered | Run initialization in a clean temp directory | The command creates only schema and directories, with no network/data-source calls | `bash scripts/acceptance-pr-03` |
| PR-03-007 | Existing build and smoke remain healthy | Run backend compile, frontend build, and smoke | Backend, frontend, MCP tool listing, and Web UI health checks pass | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-03
5 tests passed; PR-03 acceptance passed.

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
