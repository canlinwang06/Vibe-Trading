# PR-33 Acceptance Cases

## Scope

- PR: PR-33
- Branch: `codex/pr-33-signal-file-preview`
- Feature area: JoinQuant signal JSON/CSV preview and download

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-33
```

Expected result:

```text
PR-33 acceptance passed.
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
| PR-33-001 | Generate copy package with signal previews | Click `生成复制包` after a passing preflight | Page shows `信号文件预览`, `导出信号 JSON`, and `导出信号 CSV` | `bash scripts/acceptance-pr-33` |
| PR-33-002 | Preview signal file metadata | Load a mocked copy package | Page displays signals filename, content type, character count, and content preview | `bash scripts/acceptance-pr-33` |
| PR-33-003 | Download signals JSON | Click `下载 signals.json` | Browser download helper is called with the JSON file content from the local copy package | `bash scripts/acceptance-pr-33` |
| PR-33-004 | Download signals CSV | Click `下载 signals.csv` | Browser download helper is called with the CSV file content from the local copy package | `bash scripts/acceptance-pr-33` |
| PR-33-005 | Keep JoinQuant copy guardrails | Inspect implementation | The UI only downloads local files and does not open JoinQuant, submit remotely, or trade | `bash scripts/acceptance-pr-33` |
| PR-33-006 | Previous copy-review flow remains intact | Generate package and copy strategy | Copy review, strategy.py clipboard copy, and Download Python Strategy fallback still work | `bash scripts/acceptance-pr-33` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-33
19 tests passed; PR-33 acceptance passed.
```

Full verification evidence is recorded in `PR_33_REVIEW.md`.
