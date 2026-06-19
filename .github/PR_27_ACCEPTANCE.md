# PR-27 Acceptance Cases

## Scope

- PR: PR-27
- Branch: `codex/pr-27-candidate-pool-ui`
- Feature area: Candidate-pool Chinese UI

## Overall Acceptance Command

Command:

```bash
bash scripts/acceptance-pr-27
```

Expected result:

```text
PR-27 acceptance passed.
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
| PR-27-001 | Render Chinese candidate-pool page | Open `/candidate-pool` | Page shows `候选股票池`, Chinese controls, and `不生成交易信号` guardrail | `bash scripts/acceptance-pr-27` |
| PR-27-002 | Refresh candidates | Click `刷新候选` | Frontend calls `/api/candidate-pool` and renders ticker, theme, sector, source, scores, risk, and included status | `bash scripts/acceptance-pr-27` |
| PR-27-003 | Build candidate pool | Click `生成候选池` | Frontend calls `/api/candidate-pool/build` and displays rows written plus generated candidates | `bash scripts/acceptance-pr-27` |
| PR-27-004 | Manually add A-share candidate | Click `加入候选池` with default AI-chain sample | Frontend calls `/api/candidate-pool/user-add`, then refreshes candidates | `bash scripts/acceptance-pr-27` |
| PR-27-005 | Include/exclude review controls | Click `排除` or `纳入` in the table | Frontend calls include/exclude APIs with Chinese review reasons and refreshes the list | `bash scripts/acceptance-pr-27` |
| PR-27-006 | Local validation and API errors | Enter invalid limits or mock backend prerequisite errors | UI displays readable Chinese errors without live trading side effects | `bash scripts/acceptance-pr-27` |
| PR-27-007 | Navigation and route wiring | Inspect router/navigation | `/candidate-pool` uses the real CandidatePool page and keeps Chinese A-share navigation | `bash scripts/acceptance-pr-27` |
| PR-27-008 | Cost and trading guardrails | Inspect frontend implementation | No `OPENAI_API_KEY`, JoinQuant automation, approval, broker action, live runner, or live authorization is introduced | `bash scripts/acceptance-pr-27` |

## Evidence

Latest targeted run:

```text
bash scripts/acceptance-pr-27
13 tests passed; PR-27 acceptance passed.
```

Full verification evidence is recorded in `PR_27_REVIEW.md`.
