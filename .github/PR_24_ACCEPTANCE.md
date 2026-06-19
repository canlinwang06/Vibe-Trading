# PR-24 Acceptance Cases

## Scope

- PR: PR-24
- Branch: `codex/pr-24-event-reaction-study`
- Feature area: Event reaction study backend

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-24
```

Expected result:

```text
PR-24 acceptance passed.
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
| PR-24-001 | Schema support | Initialize local A-share store | `event_reactions` table exists with reaction, return, abnormal return, drawdown, volume, and breadth fields | `bash scripts/acceptance-pr-24` |
| PR-24-002 | Stock and sector reactions | Seed one AI 算力 policy event plus local stock, benchmark, and sector bars; calculate `T+1` and `T+5` | Service writes stock and sector reactions, including raw, benchmark, sector, abnormal return, max drawdown, volume change, and breadth change | `bash scripts/acceptance-pr-24` |
| PR-24-003 | AI policy T+5 summary | Summarize stock reactions for `event_subtype=AI算力`, `window=T+5` | Summary returns average raw, benchmark, sector, abnormal return, drawdown, volume, and breadth metrics | `bash scripts/acceptance-pr-24` |
| PR-24-004 | Missing prerequisites | Calculate reactions with no event mappings | Service returns a Chinese prerequisite error | `bash scripts/acceptance-pr-24` |
| PR-24-005 | API round trip | Call calculate, list, and summary routes | API returns local event reaction results and research-only guardrails | `bash scripts/acceptance-pr-24` |
| PR-24-006 | Cost and trading guardrails | Inspect PR-24 service and routes | No `OPENAI_API_KEY`, browser automation, JoinQuant remote URL, approval, live-trading, or broker order path is introduced | `bash scripts/acceptance-pr-24` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-24
10 tests passed; PR-24 acceptance passed.
```

Full verification evidence is recorded in `PR_24_REVIEW.md`.
