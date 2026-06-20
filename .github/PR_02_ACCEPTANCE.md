# PR-02 Acceptance Cases

## Scope

- PR: PR-02
- Branch: `codex/pr-02-cn-ashare-shell`
- Feature area: Chinese A-share product shell and navigation

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-02
```

Expected result:

```text
PR-02 acceptance passed.
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
| PR-02-001 | Default product shell is Chinese | Open the Web UI with no language override | Navigation and dashboard use Chinese A-share terminology | `bash scripts/acceptance-pr-02` |
| PR-02-002 | Sidebar contains only A-share product entries | Render the layout sidebar | Sidebar shows A 股驾驶舱, 事件雷达, 板块雷达, 候选股票池, 策略实验室, 回测结果, 风控组合, 交易计划, 聚宽导出, 数据源设置, 系统设置 | `bash scripts/acceptance-pr-02` |
| PR-02-003 | Legacy generic routes are hidden from sidebar | Render the layout sidebar | 智能体, 运行时, Alpha 动物园, 相关性矩阵, Sessions are not visible | `bash scripts/acceptance-pr-02` |
| PR-02-004 | Dashboard is A-share focused | Render the home page | Home title is A 股事件驱动策略驾驶舱 and cards point to A-share modules | `bash scripts/acceptance-pr-02` |
| PR-02-005 | Homepage does not show non-A-share examples | Render the home page | No crypto, AAPL, BTC, options, 美股, 港股, 加密货币, 期权 copy appears | `bash scripts/acceptance-pr-02` |
| PR-02-006 | Placeholder pages are clear but not falsely enabled | Visit new shell routes | Pages show current status and safety boundary instead of mock live data | `bash scripts/acceptance-pr-02` |
| PR-02-007 | Settings entry is Chinese | Visit 系统设置 | Page title and primary controls use Chinese text | `npm --prefix frontend run build` |
| PR-02-008 | Old routes remain direct-link compatible | Build frontend routes | Legacy pages still compile for direct links, but are no longer surfaced in the sidebar | `npm --prefix frontend run build` |
| PR-02-009 | Visible shell controls remain Chinese by default | Render the layout sidebar | The language control is shown as 切换语言 instead of English | `bash scripts/acceptance-pr-02` |

## Evidence

Latest local run:

```text
bash scripts/acceptance-pr-02
PR-02 acceptance passed.

npm --prefix frontend run test:run
213 passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.
```
