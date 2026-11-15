# Spec 0002: inventory domain core (Spike 2)

Status: final (2026-11-15).

Decision record: `docs/adr/0001-domain-code-layout.md`. Rules: AGENTS.md section 3 ("Backend layout rules"), section 6 ("Inventory", "Manual actions and admin") and section 7. Domain background: `docs/resumen-proyecto-vintage.md`, sections 4 and 12.

## Goal

A piece has a state and a channel, can be held with an expiry, and changes only through one service that is atomic in PostgreSQL and audited in the same transaction.

## Preconditions (done by the architect, not by the agent)

- The work happens on the branch the architect created for this attempt.
- The development database is migrated up to `accounts.0001_initial`.

## Scope

Create the Django app `inventory` in `backend/inventory/` and add it to `INSTALLED_APPS`.

### Models

- **Piece:** state, channel, creation time. Nothing else in this block.
  - States: `available`, `reserved`, `sold`, `withdrawn`.
  - Channels: `warehouse`, `event`, `website`, `gotrendier`.
  - Values are English identifiers. Labels are Spanish (es-MX): Disponible, Reservada, Vendida, Dada de baja; Bodega, Evento, Página propia, GoTrendier.
- **Hold:** the piece, the state and channel the piece had before the hold, the expiry, whether it was already extended, and whether it is still active.
  - The database allows at most one active hold per piece (a constraint, not only a check in Python).
- **Audit record:** piece, user (empty for automatic transitions), time, state and channel before, state and channel after, reason.
  - The service only inserts audit records. It never updates or deletes them.

Generate the migration with `python manage.py makemigrations`. Do not write it by hand.

### Service: `backend/inventory/services.py`

The only code that writes piece state, piece channel, holds or audit records. Every operation runs in one transaction, uses a conditional `UPDATE` that checks the expected state and channel, and checks the affected row count.

| Operation | From | To | Requires |
|---|---|---|---|
| Create a piece | (nothing) | `available` / `warehouse` | user, reason |
| Send to event | `available` / `warehouse` | `available` / `event` | user, reason |
| Return to warehouse | `available` / `event` | `available` / `warehouse` | user, reason |
| Place a hold | `available` / `warehouse` or `event` | `reserved`, same channel | user, reason, expiry in the future |
| Release a hold | `reserved` with an active hold | the state and channel stored in the hold | user, reason |
| Extend a hold | `reserved` with an active hold not yet extended | unchanged; new expiry | user, reason, new expiry later than the current one |
| Expire holds | `reserved` with an active hold past its expiry | the state and channel stored in the hold | no user; system reason |
| Withdraw | `available`, any channel | `withdrawn`, same channel | user, reason |

Rules for every operation:

- Any combination not in the table is rejected. A rejection raises a domain exception defined in `inventory` and changes nothing.
- A reason that is empty or only whitespace is rejected.
- Each successful operation writes exactly one audit record, except the lazy expiry below, which writes one for the expiry and one for the operation.
- If the audit insert fails, the piece and the hold stay as they were.
- **Lazy expiry:** an operation that finds the piece `reserved` with a hold past its expiry first expires that hold (as "Expire holds" does) and then continues, all in the same transaction.
- Extending a hold does not change state or channel; it still writes an audit record with the reason.

### Management command

`python manage.py expire_holds` expires every active hold past its expiry through the service and prints how many it expired.

### Tests

- Tests go in `backend/tests/inventory/`.
- Add an empty `__init__.py` to `backend/tests/`, `backend/tests/accounts/` and `backend/tests/inventory/`. Without them, two test files with the same name in different folders fail at collection.
- Tests may create rows directly to arrange a starting situation that no operation in this block can produce (for example a `sold` piece).

## Acceptance criteria

Each criterion maps to at least one test in `backend/tests/inventory/`, except AC15.

| # | Given | When | Then |
|---|---|---|---|
| AC1 | Nothing | A piece is created | It is `available` / `warehouse` and one audit record exists with empty "before" values |
| AC2 | A piece `available` / `warehouse` | It is sent to event, then returned | Each step changes only the channel and writes one audit record with user, reason, before and after |
| AC3 | A piece `available` / `event` | A hold is placed | The piece is `reserved` / `event`, and the hold stores `available` / `event` and the expiry |
| AC4 | A piece `reserved` / `event` with an active hold | The hold is released | The piece is `available` / `event` (not `warehouse`), and the hold is no longer active |
| AC5 | Two database connections and one `available` piece | Both place a hold at the same time, repeated 50 times with a fresh piece each time | In every repetition exactly one succeeds and one is rejected; there is one active hold and one hold audit record |
| AC6 | A piece that is `reserved`, `sold` or `withdrawn` | A hold is placed | It is rejected and nothing changes |
| AC7 | A piece that is `reserved` | It is sent to event, returned to warehouse or withdrawn | It is rejected and nothing changes |
| AC8 | A piece that is `sold` or `withdrawn` | Any operation in the table is attempted | It is rejected and nothing changes |
| AC9 | Any operation that requires a reason | It is called with an empty or whitespace reason | It is rejected and nothing changes |
| AC10 | An active hold never extended | It is extended twice | The first extension moves the expiry and writes an audit record; the second is rejected |
| AC11 | A piece `reserved` / `event` with a hold past its expiry | `expire_holds` runs | The piece is `available` / `event`; the audit record has no user and a system reason; running the command again changes nothing |
| AC12 | A piece `reserved` with a hold past its expiry, and the command has not run | Another hold is placed | It succeeds; two audit records are written (expiry, then new hold); the old hold is not active |
| AC13 | A hold that has not reached its expiry | `expire_holds` runs | Nothing changes |
| AC14 | The audit insert is forced to fail | A hold is placed | The operation fails, the piece is still `available`, and no hold exists |
| AC15 | The finished work | `make check` runs | It passes, including "no missing migrations" |

AC5 runs against PostgreSQL with real concurrent connections (threads, each with its own connection). It must not use mocks or SQLite.

Reviewer checks, not tests:

- No code outside `backend/inventory/services.py` assigns or updates piece state, piece channel, holds or audit records, except test arrangement.
- `inventory` imports no other project app. It refers to the user with `settings.AUTH_USER_MODEL`.

## Out of scope

Deferring these is not a conflict with AGENTS.md: section 6 rules are intent, and these arrive with later blocks.

- Selling a piece, payments, prices, money, cash closings.
- Events as an entity (name, date, hold duration per event). The expiry of a hold is a parameter.
- Reactivating an expired hold and late payments.
- Returning a `withdrawn` piece to `available`, and withdrawing a `reserved` piece.
- Permissions per action and the two-step confirmation.
- The piece public code, QR labels, catalog data (title, brand, category, size, condition, photos).
- A closed catalog of withdrawal reasons. The reason is text in this block.
- Django admin for these models, views, templates, URLs.
- Any app other than `inventory`.
- Running `migrate` or changing the development database in any way.
- New dependencies (for example a library to freeze time), `AGENTS.md`, `opencode.jsonc`.
- Commits, unless the architect asks.

## Final report

As AGENTS.md section 7 requires: what changed, which commands ran with their results, and what was not verified.
