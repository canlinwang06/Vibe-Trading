# PR-06 Acceptance Cases

## Scope

- PR: PR-06
- Branch: `codex/pr-06-event-extraction`
- Feature area: Rule-based event extraction, event clustering, and event radar query APIs

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-06
```

Expected result:

```text
PR-06 acceptance passed.
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
| PR-06-001 | Extract structured event from raw document | Insert an AI policy raw document, then run extraction | `events` receives event type, subtype, summary, sentiment, intensity, novelty, certainty, and A-share relevance score | `bash scripts/acceptance-pr-06` |
| PR-06-002 | Preserve point-in-time safety | Extract from a document published after market close | Event has `publish_time`, `crawl_time`, `knowable_time`, and next tradable `09:30` timestamp | `bash scripts/acceptance-pr-06` |
| PR-06-003 | Cluster same topic across sources | Insert the same AI policy topic from two sources | One `event_cluster` has two mentions and two sources | `bash scripts/acceptance-pr-06` |
| PR-06-004 | Query event radar events | Call `/api/event-radar/events` after extraction | API returns extracted events with A-share relevance scores | `bash scripts/acceptance-pr-06` |
| PR-06-005 | Query event clusters and details | Call `/api/event-radar/clusters` and `/api/event-radar/clusters/{cluster_id}` | API returns cluster metrics and member events | `bash scripts/acceptance-pr-06` |
| PR-06-006 | Failure is readable in Chinese | Run extraction with no raw documents | API returns a Chinese validation error | `bash scripts/acceptance-pr-06` |
| PR-06-007 | Cost guardrail is preserved | Inspect implementation and run smoke | No `OPENAI_API_KEY` or LLM API call is introduced | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-06
6 tests passed; PR-06 acceptance passed.

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
