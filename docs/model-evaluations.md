# Model evaluations

One entry per run, newest first. The protocol is in `docs/architect-handoff.md` ("Model evaluation protocol").

## 2026-11-14: `opencode/beam-free`, spec 0001 (accounts custom user)

Branch `accounts-attempt-1`, first attempt. Result: passed and merged into main.

| Check | Result |
|---|---|
| Scope | Only what the spec asked: `settings.py` (2 lines), `backend/accounts/`, `backend/tests/accounts/test_user.py`. No extra routes, fields, apps or tests. |
| Acceptance criteria | AC1 to AC4 have tests with the names in the spec. AC5 (`make check`) and AC6 (`rg`) were re-run by the reviewer and pass. |
| `make check` | Reported as run, together with the separate steps. The order could not be confirmed from the report. |
| Limits | No commit, no dependency or lockfile change, no `migrate`, database untouched. |
| Language | Code and tests in English, report in Spanish. |
| Final report | Matched the diff. Separated what was not verified. |
| Manual test by the architect | Migrations applied in the expected order, `auth_user` table absent, user admin works. |

Cost and behavior, from the OpenCode session panel:

- 24 messages (1 user, 22 assistant), about 1 minute, cost 0.00 USD.
- Tokens shown: 20,709 total (407 in, 292 out, 42 reasoning, 19,968 cache read). The panel reports 2% context use, so these look like the size of the last request, not the sum over the session. Cumulative tokens were not captured.
- Retries after the same failure: not captured.

Minor observations, none blocking:

- `models.py` has a redundant `pass` after the docstring.
- The AC1 test imports `User` inside the function.
- `backend/tests/accounts/` has no `__init__.py`.

Compared with the health endpoint task (see the handoff): this time the model stayed inside the scope. The difference is a spec with an explicit out-of-scope section.
