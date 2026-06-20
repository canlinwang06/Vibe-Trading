# PR-37 Acceptance: Complete Event And Sector Radar Pages

## Scope

Replace the remaining user-visible A-share placeholder routes with working Chinese radar pages:

- `/event-radar` imports local documents, extracts structured events, maps events to sectors/stocks, and refreshes local radar context.
- `/sector-radar` generates sector heat scores from mapped events and shows score details plus mapping context.
- The home page no longer says core modules are future work.

## Acceptance Cases

| ID | Case | How To Verify | Expected Result |
| --- | --- | --- | --- |
| PR-37-001 | Event radar route is real | Inspect `frontend/src/router.tsx` | `/event-radar` imports `@/pages/EventRadar`, not `AsharePlaceholder` |
| PR-37-002 | Sector radar route is real | Inspect `frontend/src/router.tsx` | `/sector-radar` imports `@/pages/SectorRadar`, not `AsharePlaceholder` |
| PR-37-003 | Event radar actions work | Run `EventRadar.test.tsx` | Import, extraction, mapping, refresh, validation, and API errors are covered |
| PR-37-004 | Sector radar actions work | Run `SectorRadar.test.tsx` | Score generation, refresh, validation, and API errors are covered |
| PR-37-005 | Browser radar flow works | Run `bash scripts/acceptance-pr-37` | Browser imports AI industry-chain document, extracts/maps events, generates sector scores, and sees no stale waiting copy |
| PR-37-006 | No stale waiting copy remains | Run `bash scripts/acceptance-pr-37` | No active UI says `等待 PR` or `后续模块接入` |
| PR-37-007 | Cost and trading guardrails hold | Run `bash scripts/acceptance-pr-37` and `bash scripts/smoke` | No model API key requirement, browser JoinQuant automation, or live trading action is introduced |
| PR-37-008 | Build still passes | Run frontend and backend checks | `npm --prefix frontend run build` and `.venv/bin/python -m compileall -q agent` pass |

## Command

```bash
bash scripts/acceptance-pr-37
```
