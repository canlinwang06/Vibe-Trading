# PR-05 Acceptance Cases

## Scope

- PR: PR-05
- Branch: `codex/pr-05-event-source-ingestion`
- Feature area: Event radar source registry, manual collection, and raw-document ingestion

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-05
```

Expected result:

```text
PR-05 acceptance passed.
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
| PR-05-001 | Default event sources are seeded | Initialize/list event radar sources | Policy, announcement, finance-news, and social-hot source categories exist | `bash scripts/acceptance-pr-05` |
| PR-05-002 | Manual collection writes raw documents | POST documents to `/api/event-radar/collect/run` | Documents are persisted into `raw_documents` | `bash scripts/acceptance-pr-05` |
| PR-05-003 | Raw documents keep point-in-time fields | Insert a document with `publish_time` | Stored row includes `publish_time`, `crawl_time`, and `content_hash` | `bash scripts/acceptance-pr-05` |
| PR-05-004 | Duplicate documents are skipped | Submit the same document twice | First insert succeeds; duplicate is reported without a second row | `bash scripts/acceptance-pr-05` |
| PR-05-005 | Manual API routes are mounted | Inspect FastAPI route table | `/api/event-radar/sources`, `/api/event-radar/raw-documents`, and `/api/event-radar/collect/run` exist | `bash scripts/acceptance-pr-05` |
| PR-05-006 | Failure is readable in Chinese | Submit a document with an unknown source | API returns a Chinese validation error | `bash scripts/acceptance-pr-05` |
| PR-05-007 | Cost guardrail is preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY` or LLM API call is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-05
6 tests passed; PR-05 acceptance passed.

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
