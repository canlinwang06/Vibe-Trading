# Codex PR Workflow

This repository is being adapted into a local A-share event strategy research workbench. Each PR must be small enough to review and validate independently.

## Required PR Gates

1. Product scope is clear and matches the PR breakdown.
2. Code review is complete before acceptance testing.
3. Review output is grouped into `Blocker`, `Important`, and `Follow-up`.
4. No unresolved `Blocker` remains.
5. Overall smoke test passes.
6. Targeted acceptance tests for the current PR pass.
7. The project still builds and runs from Visual Studio Code.
8. Changes remain inside the current local Git project and can be archived to GitHub.

## Standard Local Commands

```bash
bash scripts/smoke
```

The smoke command checks provider guardrails, backend compilation, frontend build, MCP tool listing, and the local web UI.

## Review And Acceptance Templates

- Review template: `.github/PR_REVIEW_TEMPLATE.md`
- Acceptance template: `.github/PR_ACCEPTANCE_TEMPLATE.md`

Use both for every PR.
