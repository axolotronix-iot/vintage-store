# Model evaluations

One entry per run, newest first. The protocol is in `docs/architect-handoff.md` ("Model evaluation protocol").

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
