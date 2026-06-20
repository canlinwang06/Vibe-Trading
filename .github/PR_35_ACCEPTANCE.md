# PR-35 Acceptance Cases

## Scope

- PR: PR-35
- Branch: `codex/pr-35-data-sources-ui`
- Feature area: Chinese data-source settings UI

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-35
```

Expected result:

```text
PR-35 acceptance passed.
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
| PR-35-001 | Open the data-source page | Navigate to `/data-sources` | The page shows Chinese data-source status, credential management, and safety boundary sections | `bash scripts/acceptance-pr-35` |
| PR-35-002 | Save a Tushare token | Enter a token and click `保存数据源设置` | The UI calls the local settings API, clears the input, and never renders the token plaintext | `bash scripts/acceptance-pr-35` |
| PR-35-003 | Clear a saved Tushare token | Select `清除已保存的 Tushare token` and save | The input is disabled and the API receives `clear_tushare_token: true` | `bash scripts/acceptance-pr-35` |
| PR-35-004 | Refresh local data-source status | Click `刷新状态` | The UI reloads the local settings endpoint and updates saved/not-saved state | `bash scripts/acceptance-pr-35` |
| PR-35-005 | Preserve cost and trading guardrails | Inspect implementation | The page keeps free/local data priority, does not introduce model API keys, and does not add live trading or external JoinQuant automation | `bash scripts/acceptance-pr-35` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-35
11 tests passed; PR-35 acceptance passed.
```

Full verification evidence is recorded in `PR_35_REVIEW.md`.
