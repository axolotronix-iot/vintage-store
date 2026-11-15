# Spec 0002: inventory domain core (Spike 2)

Status: final, revision 2 (2026-11-15). Revision 1 left names and signatures open; attempt 1 filled the gap with guesses. This revision fixes the public names, the tests and the deletion rules.

Decision record: `docs/adr/0001-domain-code-layout.md`. Rules: AGENTS.md section 3 ("Backend layout rules"), section 6 ("Inventory", "Manual actions and admin") and section 7. Domain background: `docs/resumen-proyecto-vintage.md`, sections 4 and 12.

## Goal

A piece has a state and a channel, can be held with an expiry, and changes only through one service that is atomic in PostgreSQL and audited in the same transaction.

## Preconditions (done by the architect, not by the agent)

- The work happens on the branch the architect created for this attempt.
- The development database is migrated up to `accounts.0001_initial`.

## Names are exact

Use exactly the model, field, function, parameter, exception and test names in this spec.

- No aliases, no alternative names, no `*args` or `**kwargs` in the public functions, no guessing of argument order or type.
- There are no hidden tests. The only tests are the ones this spec lists and you write.
- A helper that this spec does not name may have any name, but it is private (leading underscore).

## Scope

Create the Django app `inventory` in `backend/inventory/` and add it to `INSTALLED_APPS`.

### Models (`backend/inventory/models.py`)

Enums, as `TextChoices`. Values are English; labels are Spanish (es-MX).

- `PieceState`: `available` (Disponible), `reserved` (Reservada), `sold` (Vendida), `withdrawn` (Dada de baja).
- `PieceChannel`: `warehouse` (Bodega), `event` (Evento), `website` (Página propia), `gotrendier` (GoTrendier).

| Model | Fields |
|---|---|
| `Piece` | `state`, `channel`, `created_at` |
| `Hold` | `piece`, `previous_state`, `previous_channel`, `expires_at`, `extended` (boolean), `active` (boolean), `created_at` |
| `PieceTransition` (the audit record) | `piece`, `user` (nullable), `created_at`, `from_state`, `from_channel`, `to_state`, `to_channel`, `reason` |

- The database allows at most one active hold per piece: a conditional unique constraint, not only a check in Python.
- `from_state` and `from_channel` are empty strings only on the record that creates a piece.
- Every foreign key in these models uses `on_delete=PROTECT`. A piece or a user that has holds or audit records cannot be deleted.
- No properties or methods on the models other than `__str__`.

Generate the migration with `python manage.py makemigrations`. Do not write it by hand.

### Exceptions (`backend/inventory/exceptions.py`)

- `InventoryError(Exception)`: base class. Every rejection raises it or a subclass.
- Subclasses are allowed if they help; each is used at least once.

### Service (`backend/inventory/services.py`)

The only code that writes piece state, piece channel, holds or audit records. These are the public functions; all parameters after `piece` are keyword-only.

```python
def create_piece(*, user, reason) -> Piece
def send_to_event(piece, *, user, reason) -> Piece
def return_to_warehouse(piece, *, user, reason) -> Piece
def place_hold(piece, *, user, reason, expires_at) -> Hold
def release_hold(piece, *, user, reason) -> Piece
def extend_hold(piece, *, user, reason, expires_at) -> Hold
def withdraw(piece, *, user, reason) -> Piece
def expire_holds() -> int
```

| Function | From | To |
|---|---|---|
| `create_piece` | (nothing) | `available` / `warehouse` |
| `send_to_event` | `available` / `warehouse` | `available` / `event` |
| `return_to_warehouse` | `available` / `event` | `available` / `warehouse` |
| `place_hold` | `available` / `warehouse` or `event` | `reserved`, same channel |
| `release_hold` | `reserved` with an active hold not past its expiry | the state and channel stored in the hold |
| `extend_hold` | `reserved` with an active hold, not past its expiry and not yet extended | unchanged; new `expires_at`, `extended` becomes true |
| `withdraw` | `available`, any channel | `withdrawn`, same channel |
| `expire_holds` | every `reserved` piece with an active hold past its expiry | the state and channel stored in the hold; returns how many holds it expired |

Rules:

- **Rejection.** Any combination not in the table raises `InventoryError` and changes nothing: the piece keeps its state and channel, and no hold or audit record is created or modified.
- **User.** `user` must be a saved user. `None` or anything else is rejected. Only `expire_holds` and the lazy expiry write a record with no user.
- **Reason.** A reason that is not a string, is empty, or is only whitespace is rejected.
- **Expiry.** `expires_at` must be a timezone-aware datetime. For `place_hold` it must be in the future; for `extend_hold` it must be later than the current `expires_at`. Otherwise the call is rejected.
- **Atomicity.** Each function runs in one transaction. A conditional `UPDATE` that filters on the expected state and channel, plus its affected row count, decides whether the change happens. Locking the piece row with `select_for_update` before reading the hold is allowed; it does not replace the conditional `UPDATE`.
- **One writer.** One private function performs the conditional `UPDATE` and inserts the `PieceTransition`. Every public function goes through it; do not repeat that code per operation.
- **Audit.** Each successful call writes exactly one `PieceTransition`, except a call that triggers the lazy expiry, which writes two. `extend_hold` writes a record whose "from" and "to" values are equal. Audit records are only inserted, never updated or deleted. If the insert fails, nothing else is kept.
- **Lazy expiry.** `send_to_event`, `return_to_warehouse`, `place_hold` and `withdraw`, when they find the piece `reserved` with a hold past its expiry, first expire that hold exactly as `expire_holds` does and then continue in the same transaction. If the call is then rejected, the expiry is rolled back with it.
- **System reason.** Expiry records have no user and the reason `Hold expired`.

### Management command

`python manage.py expire_holds` calls `services.expire_holds()` and prints `Apartados expirados: <n>`.

## Tests

- One file: `backend/tests/inventory/test_services.py`. One test per acceptance criterion, with the name in the table. A criterion that covers several cases uses `pytest.mark.parametrize`.
- Add an empty `__init__.py` to `backend/tests/`, `backend/tests/accounts/` and `backend/tests/inventory/`.
- Tests assert `InventoryError` (or a subclass) for rejections, never `ValueError` or `Exception`.
- "Nothing changes" is asserted every time: same state and channel after `refresh_from_db()`, same number of holds, same number of audit records.
- Tests may write rows directly only to arrange a situation no function in this block can produce: a `sold` piece, or a hold whose `expires_at` is in the past.

## Acceptance criteria

| # | Given | When | Then | Test |
|---|---|---|---|---|
| AC1 | Nothing | `create_piece` | The piece is `available` / `warehouse`; one audit record with empty "from" values, the user and the reason | `test_create_piece` |
| AC2 | A piece `available` / `warehouse` | `send_to_event`, then `return_to_warehouse` | Each call changes only the channel and writes one record with the user, the reason and the correct "from" and "to" values | `test_send_to_event_and_return` |
| AC3 | A piece `available` / `event` | `place_hold` | The piece is `reserved` / `event`; the hold stores `available` / `event` and `expires_at`, is active and not extended | `test_place_hold_keeps_channel` |
| AC4 | A piece `reserved` / `event` with an active hold | `release_hold` | The piece is `available` / `event`, not `warehouse`; the hold is not active | `test_release_hold_restores_previous` |
| AC5 | Two database connections and one `available` piece | Both call `place_hold` at the same time; the test repeats this 50 times in a loop, with a new piece each time | In every repetition exactly one call succeeds and the other raises `InventoryError`; there is one active hold and one record with `to_state` `reserved` | `test_concurrent_holds_single_winner` |
| AC6 | A piece that is `reserved` (hold not past its expiry), `sold` or `withdrawn` | `place_hold` | Rejected; nothing changes | `test_place_hold_rejected` |
| AC7 | A piece that is `reserved` with a hold not past its expiry | `send_to_event`, `return_to_warehouse` or `withdraw` | Rejected; nothing changes | `test_reserved_rejects_moves_and_withdraw` |
| AC8 | A piece that is `sold` or `withdrawn` | Each of `send_to_event`, `return_to_warehouse`, `place_hold`, `release_hold`, `extend_hold`, `withdraw` | Rejected; nothing changes | `test_sold_or_withdrawn_rejects_everything` |
| AC9 | Each function that takes a reason | It is called with `""`, with `"   "` and with `None` | Rejected; nothing changes | `test_reason_is_required` |
| AC10 | Each function that takes a user | It is called with `user=None` | Rejected; nothing changes | `test_user_is_required` |
| AC11 | An active hold never extended | `extend_hold` twice | The first call moves `expires_at`, sets `extended` and writes one record with equal "from" and "to"; the second is rejected and changes nothing | `test_extend_hold_only_once` |
| AC12 | A piece `reserved` / `event` with a hold past its expiry | The `expire_holds` command runs twice | After the first run the piece is `available` / `event`, the hold is not active, and the new record has no user and the reason `Hold expired`; the second run changes nothing; the output reports 1, then 0 | `test_expire_holds_command` |
| AC13 | A hold not past its expiry | The `expire_holds` command runs | Nothing changes; the output reports 0 | `test_expire_holds_ignores_live_holds` |
| AC14 | A piece `reserved` with a hold past its expiry; the command has not run | `place_hold` | It succeeds; two records are written, the expiry and then the new hold; the old hold is not active and the new one is | `test_lazy_expiry_on_place_hold` |
| AC15 | A hold past its expiry; the command has not run | `release_hold` or `extend_hold` | Rejected; nothing changes | `test_expired_hold_cannot_be_released_or_extended` |
| AC16 | The audit insert is forced to fail | `place_hold` | The call fails; the piece is still `available`; no hold exists | `test_audit_failure_rolls_back` |
| AC17 | A piece with audit records, and the user in them | Each is deleted | Each delete raises `ProtectedError`; the audit records are intact | `test_audit_blocks_deletion` |
| AC18 | The finished work | `make check` | It passes, including "no missing migrations" | command output in the final report |

AC5 runs against PostgreSQL with real threads, each with its own connection. It must not use mocks or SQLite.

Reviewer checks, not tests:

- No code outside `backend/inventory/services.py` writes piece state, piece channel, holds or audit records, except the test arrangement allowed above.
- `inventory` imports no other project app. It refers to the user with `settings.AUTH_USER_MODEL`.
- No aliases, and no public name that this spec does not list.

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

As AGENTS.md section 7 requires: what changed, which commands ran with their results, and what was not verified. Also list every acceptance criterion with the test that covers it. If a criterion is not covered, say so; do not claim it.
