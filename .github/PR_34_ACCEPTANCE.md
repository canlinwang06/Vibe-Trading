# PR-34 Acceptance Cases

## Scope

- PR: PR-34
- Branch: `codex/pr-34-copy-package-download`
- Feature area: JoinQuant complete copy-package manifest and download

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-34
```

Expected result:

```text
PR-34 acceptance passed.
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
| PR-34-001 | Generate copy package with package manifest | Click `生成复制包` after a passing preflight | Page shows `复制包清单`, file count, content size, package filename, and local-only boundary | `bash scripts/acceptance-pr-34` |
| PR-34-002 | Download complete local copy package | Click `下载完整复制包` | Browser download helper is called with an `application/json` package containing manifest, validation, files, and guardrails | `bash scripts/acceptance-pr-34` |
| PR-34-003 | Package manifest lists generated files | Load a mocked copy package | Page lists strategy.py, signals.json, signals.csv, README.md, content type, and size | `bash scripts/acceptance-pr-34` |
| PR-34-004 | Previous signal previews remain intact | Generate package | JSON/CSV preview and individual signal downloads remain visible | `bash scripts/acceptance-pr-34` |
| PR-34-005 | Keep JoinQuant export guardrails | Inspect implementation | The UI only downloads local package files and does not open JoinQuant, submit remotely, or trade | `bash scripts/acceptance-pr-34` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-34
20 tests passed; PR-34 acceptance passed.
```

Full verification evidence is recorded in `PR_34_REVIEW.md`.
