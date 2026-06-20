# PR-37 Review: Complete Event And Sector Radar Pages

## Summary

Delivered:

- Replaced the remaining active placeholder routes for event radar and sector radar with real Chinese workbench pages.
- Added typed frontend API methods for event source/document collection, event extraction, event mapping, sector mappings, theme map, and sector scoring.
- Updated the home page status so it reflects the current connected research flow.
- Added PR-specific frontend tests and an acceptance script for route wiring, UI coverage, stale-copy checks, and guardrails.

## Review Checklist

- [x] `/event-radar` no longer routes to `AsharePlaceholder`.
- [x] `/sector-radar` no longer routes to `AsharePlaceholder`.
- [x] Event radar can call local document import, extraction, mapping, and refresh APIs.
- [x] Sector radar can call local sector scoring and score refresh APIs.
- [x] Empty states are explicit and do not imply an unfinished PR.
- [x] UI remains Chinese.
- [x] No `OPENAI_API_KEY` requirement is added.
- [x] No live broker action, JoinQuant browser automation, or live-trading copy is added.

## Residual Risk

- The pages show empty states when the local A-share store has not yet been seeded. This is intentional; running the daily workflow or importing a document from the event radar page populates the data.
- Sector scoring depends on completed event mapping. If mapping is missing, the backend returns a Chinese blocking message and the page displays it.

## Verification

- `bash scripts/acceptance-pr-37`
- Full build, smoke, and browser checks are expected before merging.
