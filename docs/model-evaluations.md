# Model evaluations

One entry per run, newest first. The protocol is in `docs/architect-handoff.md` ("Model evaluation protocol").

## 2026-11-15: `opencode/beam-free`, spec 0002 revision 2 (inventory domain core), attempt 2

Branch `inventory-attempt-2`, new session. Result: passed after one correction pass, merged into main.

| Check | Result |
|---|---|
| Scope | Respected: only the `inventory` app, `settings.py` (1 line) and the three `__init__.py` files the spec asks for. |
| Public interface | Exact names and keyword-only signatures. No aliases, no `*args` or `**kwargs`. |
| Domain rules | One private function does the conditional `UPDATE` and the audit insert. A missing or unsaved user is rejected. Every foreign key is `PROTECT`. |
| Tests | The 17 named tests exist; AC5 repeats 50 times. One extra test, `test_expires_at_validation`, covers the expiry rule, which has no criterion in the spec. |
| `make check` | Run literally in both passes. Passes (39 tests after the correction). |
| Limits | No commit, no `migrate`, no dependency change. |
| Final report | Accurate, with the criterion-to-test table. It reported "1 warning" without saying what it was. |
| Mechanism | Sound. Reviewer probes passed: a 50-repetition race with a barrier, rollback of the lazy expiry when the call is rejected, rollback when the audit insert fails. |
| Manual test by the architect | Create, send to event, hold, two rejections, release, hold and expiry by the command gave the expected states and six audit records, the last one with no user. |

Defects found in review and fixed in the correction pass, same session:

- The AC5 test left its thread connections open: pytest could not drop `test_vintage` and warned about it. It also had no barrier.
- One test contained only `pass`.
- The AC9 and AC10 cases for `return_to_warehouse`, `release_hold` and `extend_hold` used a piece that would be rejected anyway. After the fix, disabling either validator makes all seven cases of its test fail.
- Every function turned `IntegrityError` into `InventoryError`, and the AC16 test depended on it.

Cost and behavior, from `opencode session export`:

| | Implementation | Correction pass |
|---|---|---|
| Assistant steps | 36 | 46 |
| Tokens in | 73,689 | 112,290 |
| Tokens out | 9,634 | 6,935 |
| Reasoning tokens | 7,462 | 2,886 |
| Cache read | 985,344 | 2,210,816 |
| Tool calls (failed) | 43 (2) | 45 (1) |

- Cost 0.00 USD. The implementation took 311 seconds; the correction pass has no usable duration because it includes waits for approval.
- Fixing four small defects cost more than writing the block. The model edited files with `python3 - <<EOF` scripts and `sed -i` instead of the edit tool. One global replace changed the expected exception in two unrelated tests, and it needed seven `pytest` runs to repair them.
- It prefixes almost every command with `cd /workspace/backend &&`, so allowed commands (`pytest`, `ruff`) asked for approval too. OpenCode asked the architect for every chained command.
- The reasoning mentions hidden tests once, against 97 times in attempt 1.

Rule changes from this run: AGENTS.md section 4 now forbids editing files from the shell and chaining commands.

Left as follow-ups, none blocking:

- The AC9 and AC10 tests do not assert the state and channel of the piece after the rejection.
- `expire_holds` locks every reserved piece in one transaction and repeats the logic of the lazy expiry.
- `test_expires_at_validation` is not in the spec.

## 2026-11-15: `opencode/beam-free`, spec 0002 revision 1 (inventory domain core), attempt 1

Branch `inventory-attempt-1`, kept but not merged. Result: failed the architect's review.

| Check | Result |
|---|---|
| Scope | Respected: only the `inventory` app, no admin, no extra apps. |
| `make check` | Run literally, twice. Passes (20 tests). |
| Limits | No commit, no `migrate`, no dependency change. No failed or denied tool calls. |
| Public interface | Failed. Every service function takes `*args, **kwargs` and guesses each argument by type. About 30 aliases for functions, models, exceptions and properties, commented as names "hidden tests might use". |
| Domain rules | Manual operations accept a missing user. Audit records are deleted with their piece (`CASCADE`); the user is set to null when deleted. |
| Tests | AC5 runs once instead of 50 times. AC13 has no test. Rejections are asserted with `ValueError`. "Nothing changes" is rarely asserted. |
| Design | The conditional `UPDATE` plus audit insert is repeated in six functions; ADR 0001 asks for one private function. |
| Final report | Inaccurate: it claims AC1 to AC14 are covered. |
| Mechanism | Sound. A reviewer probe with 50 repetitions and real connections gave one winner every time. |

Cost and behavior, from `opencode session export`:

- 47 assistant steps, 350 seconds, cost 0.00 USD.
- Tokens: 123,171 in, 13,715 out, 14,143 reasoning, 2,153,024 cache read.
- The run reused the session of spec 0001 instead of a new one.
- The model's reasoning mentions hidden tests 97 times: it treated the task as an exam.

Causes on our side, fixed in revision 2 of the spec: it did not name the public functions, the models or the tests, and it did not say what happens to audit records on deletion.

## 2026-11-14: `opencode/beam-free`, spec 0001 (accounts custom user)

Branch `accounts-attempt-1`, first attempt. Result: passed and merged into main.

| Check | Result |
|---|---|
| Scope | Only what the spec asked: `settings.py` (2 lines), `backend/accounts/`, `backend/tests/accounts/test_user.py`. No extra routes, fields, apps or tests. |
| Acceptance criteria | AC1 to AC4 have tests with the names in the spec. AC5 (`make check`) and AC6 (`rg`) were re-run by the reviewer and pass. |
| `make check` | Run literally at the end (step 19), after running every step separately as well. |
| Limits | No commit, no dependency or lockfile change, no `migrate`, database untouched. |
| Language | Code and tests in English, report in Spanish. |
| Final report | Matched the diff. Separated what was not verified. |
| Manual test by the architect | Migrations applied in the expected order, `auth_user` table absent, user admin works. |

Cost and behavior, from `opencode session export`:

- 22 assistant steps, 85 seconds, cost 0.00 USD.
- Tokens: 44,605 in, 1,932 out, 2,358 reasoning, 332,160 cache read. The session panel shows only the last request (20,709 tokens), not this total.
- One retry: five file writes failed on a malformed path and were corrected in the next step.
- The agent ran commands outside the allowlist in AGENTS.md section 4 (`cat`, `find`, `git branch -a`, `manage.py showmigrations`), mostly chained after `cd`. The export does not show whether OpenCode asked for approval.

Minor observations, none blocking:

- `models.py` has a redundant `pass` after the docstring.
- The AC1 test imports `User` inside the function.
- `backend/tests/accounts/` has no `__init__.py`.

Compared with the health endpoint task (see the handoff): this time the model stayed inside the scope. The difference is a spec with an explicit out-of-scope section.
