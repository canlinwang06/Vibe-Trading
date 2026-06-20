## Summary

<!-- What does this PR do? 1-3 bullet points. -->

-

## Why

<!-- What problem does it solve? Link related issues with "Closes #123". -->

## Changes

<!-- List key changes. For new skills/presets, describe what they cover. -->

-

## Test Plan

- [ ] Existing tests pass (`pytest --ignore=agent/tests/e2e_backtest --tb=short -q`)
- [ ] PR smoke test passes (`bash scripts/smoke`)
- [ ] Targeted acceptance cases were added or updated using `.github/PR_ACCEPTANCE_TEMPLATE.md`
- [ ] New tests added (if applicable)
- [ ] Tested manually (describe below)

## Review Gate

- [ ] Code review completed using `.github/PR_REVIEW_TEMPLATE.md`
- [ ] No unresolved Blocker findings remain
- [ ] Important findings are fixed or explicitly moved to Follow-up

## Checklist

- [ ] No changes to protected areas (`src/agent/`, `src/session/`, `src/providers/`) without prior discussion
- [ ] No hardcoded values (API keys, file paths, magic numbers)
- [ ] No `OPENAI_API_KEY` added or required
- [ ] No live trading or broker auto-submit behavior added
- [ ] Visual Studio Code can open the project and run build/start tasks
- [ ] Code follows [CONTRIBUTING.md](../CONTRIBUTING.md) guidelines
- [ ] Documentation updated (if user-facing change)
