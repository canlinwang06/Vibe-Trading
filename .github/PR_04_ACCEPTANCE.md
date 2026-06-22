# PR-04 Acceptance Cases

## Scope

- PR: PR-04
- Branch: `codex/pr-04-ashare-market-data`
- Feature area: A-share asset master data, daily market data, and manual update API

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-04
```

Expected result:

```text
PR-04 acceptance passed.
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
| PR-04-001 | Query required A-share assets | Call `/ashare/assets/{ticker}` for `600519.SH`, `300750.SZ`, and `000001.SZ` | Each response returns `market=CN_A`, exchange, asset type, and ticker name | `bash scripts/acceptance-pr-04` |
| PR-04-002 | Required benchmark indexes are seeded | Initialize the asset master | 沪深300, 中证全指, and 创业板指 exist as index assets | `bash scripts/acceptance-pr-04` |
| PR-04-003 | Manual market-data update API is mounted | Inspect FastAPI route table | `/ashare/market-data/update` exists | `bash scripts/acceptance-pr-04` |
| PR-04-004 | Manual update writes daily bars | Trigger update with a mocked AKShare/local frame | `market_daily` receives rows for the requested date window | `bash scripts/acceptance-pr-04` |
| PR-04-005 | Daily bars contain required fields | Query `/ashare/market-daily` after update | Rows include open/high/low/close/volume/amount | `bash scripts/acceptance-pr-04` |
| PR-04-006 | Limit-up and suspension fields are handled | Write a frame with a limit-up day and a zero-volume day | `limit_status` and `suspended` are stored | `bash scripts/acceptance-pr-04` |
| PR-04-007 | Failure is readable in Chinese | Request an invalid ticker such as `BTC-USDT` | API returns a Chinese validation error | `bash scripts/acceptance-pr-04` |
| PR-04-008 | Existing build and smoke remain healthy | Run backend compile, frontend build, and smoke | Backend, frontend, MCP tool listing, and Web UI health checks pass | `bash scripts/smoke` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-04
7 tests passed; PR-04 acceptance passed.

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
