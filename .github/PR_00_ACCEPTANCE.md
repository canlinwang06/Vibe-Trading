# PR-00 Acceptance Cases

## Scope

- PR: PR-00
- Branch: `codex/pr-00-baseline`
- Feature area: local development, review, and smoke-test baseline

## Overall Smoke Test

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
| PR-00-001 | Provider guardrails reject API-key mode | Read `agent/.env` without printing secrets | Provider is `openai-codex`; `OPENAI_API_KEY` is empty or absent | `bash scripts/smoke` |
| PR-00-002 | Backend import baseline compiles | Compile the `agent` package | Python compile step exits successfully | `bash scripts/smoke` |
| PR-00-003 | Frontend build baseline compiles | Run frontend production build | TypeScript and Vite build exit successfully | `bash scripts/smoke` |
| PR-00-004 | MCP entrypoint is usable | Start MCP over stdio and list tools | Required tools include `list_skills` and `backtest` | `bash scripts/smoke` |
| PR-00-005 | Web UI baseline responds | Reach local backend UI and settings endpoint | UI shell contains `Vibe-Trading`; LLM provider is `openai-codex` | `bash scripts/smoke` |
| PR-00-006 | VS Code has PR validation task | Open VS Code task list | `Vibe-Trading: PR Smoke Test` and `Vibe-Trading: PR Gate` are available | Manual VS Code check |
| PR-00-007 | PR review and acceptance templates exist | Inspect `.github` templates | Review template includes Blocker / Important / Follow-up; acceptance template includes smoke and targeted cases | Manual file check |

## Evidence

Latest local run:

```text
bash -n scripts/smoke && bash scripts/smoke
PR smoke test passed.
```
