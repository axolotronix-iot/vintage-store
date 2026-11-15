# Spec 0003: piece public code

Status: final (2026-11-15).

Decision record: `docs/adr/0002-piece-public-code.md`. Rules: AGENTS.md section 3 ("Backend layout rules"), section 4, section 6 ("Inventory") and section 7. This block changes the code written for `docs/specs/0002-inventory-domain-core.md`; that spec stays valid.

## Goal

Every piece has a public code from the moment it is created. The block also closes three findings from the review of spec 0002.

## Preconditions (done by the architect, not by the agent)

- The work happens on the branch the architect created for this attempt.
- The development database is migrated up to `inventory.0001_initial` and contains pieces.

## Names are exact

Use exactly the field, constant, function, migration and test names in this spec.

- No aliases, no alternative names, no `*args` or `**kwargs` in public functions.
- There are no hidden tests. The only tests are the ones this spec lists and the ones that already exist.
- A helper that this spec does not name may have any name, but it is private (leading underscore).

## Scope

Only the `inventory` app and its tests.

### Model (`backend/inventory/models.py`)

Add, at module level:

```python
PUBLIC_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
PUBLIC_CODE_LENGTH = 6

def generate_public_code() -> str
```

- `generate_public_code` returns `PUBLIC_CODE_LENGTH` characters chosen from `PUBLIC_CODE_ALPHABET` with the `secrets` module. It does not query the database.
- `Piece.public_code`, in its final form: `CharField(max_length=6, unique=True, editable=False, default=generate_public_code)`.
- `Piece.__str__` starts with the public code and does not show the database id.

### Migrations

The table already has rows, so the field arrives in three migrations, in this order. Create each one with the command shown; only the second is edited by hand.

| Migration | How | Content |
|---|---|---|
| `0002_piece_public_code_nullable` | Declare the field as `CharField(max_length=6, null=True, editable=False)`, then `python manage.py makemigrations inventory -n piece_public_code_nullable` | `AddField` |
| `0003_fill_piece_public_code` | `python manage.py makemigrations inventory --empty -n fill_piece_public_code`, then write the operation | `RunPython` that gives every piece without a code a different code. The reverse operation is `migrations.RunPython.noop` |
| `0004_piece_public_code_unique` | Change the field to its final form, then `python manage.py makemigrations inventory -n piece_public_code_unique` | `AlterField` |

- The fill function gets the model with `apps.get_model("inventory", "Piece")`. It may import `generate_public_code` from `inventory.models`.
- Two pieces never receive the same code in the fill, even if the generator repeats a value.
- Do not edit `0001_initial`.

### Service (`backend/inventory/services.py`)

Add `PUBLIC_CODE_MAX_ATTEMPTS = 5`.

`create_piece` keeps its signature and its rules from spec 0002, and now:

- It calls `generate_public_code()` and passes the result when it inserts the piece. Import the function into `services.py` with `from .models import generate_public_code`, so that tests can replace `inventory.services.generate_public_code`.
- If the insert fails with `IntegrityError`, it tries again with a new code. Each insert runs in its own savepoint.
- After `PUBLIC_CODE_MAX_ATTEMPTS` failed inserts it raises `InventoryError` (or a subclass) and changes nothing: no piece and no audit record.
- No other function writes `public_code`. It never changes after the piece is created.

`expire_holds` keeps its signature, its return value and its rules from spec 0002, and now:

- It handles each hold past its expiry in its own transaction, in ascending order of hold id, and locks only the row of that piece.
- Inside that transaction it reads the hold again. If the hold is no longer active or the piece is no longer `reserved`, it skips it and does not count it.
- If one hold fails, the error propagates. Holds expired before it stay expired.
- One private function expires a hold (deactivates it and calls the private transition function with the system reason). Both `expire_holds` and the lazy expiry use it; do not repeat that code.

## Tests

New file `backend/tests/inventory/test_public_code.py` for AC1 to AC6. AC7 goes in `backend/tests/inventory/test_services.py`.

- Tests assert `InventoryError` (or a subclass) for rejections, never `ValueError` or `Exception`.
- "Nothing changes" means: same number of pieces, same number of holds and same number of audit records.
- Tests may write rows directly only to arrange a situation no service function can produce: a second piece with a chosen code, or a hold whose `expires_at` is in the past.

Changes to the existing tests in `test_services.py`:

- `test_reason_is_required` and `test_user_is_required`: for every function that receives a piece, also assert that the state and the channel of the piece are the same after `refresh_from_db()`.
- `test_expires_at_validation` is now required. After every rejection it also asserts that the state and channel of the piece, the number of holds and the number of audit records are the same.
- No other existing test changes, except where this spec makes it fail.

## Acceptance criteria

| # | Given | When | Then | Test |
|---|---|---|---|---|
| AC1 | Nothing | `create_piece` | `public_code` has 6 characters, all from `PUBLIC_CODE_ALPHABET`; `str(piece)` starts with it | `test_create_piece_assigns_public_code` |
| AC2 | Nothing | `generate_public_code()` is called 1000 times | Every result has 6 characters, all from the alphabet; at least 990 results are different | `test_generate_public_code_format` |
| AC3 | A piece | A second piece is inserted directly with the same `public_code` | The database raises `IntegrityError` | `test_public_code_unique_in_database` |
| AC4 | A piece; `inventory.services.generate_public_code` is replaced to return that piece's code once and then a new valid code | `create_piece` | It succeeds with the new code; exactly one new piece and one new audit record | `test_create_piece_retries_on_collision` |
| AC5 | A piece; the generator is replaced to always return that piece's code | `create_piece` | It raises `InventoryError`; the generator was called exactly 5 times; nothing changes | `test_create_piece_gives_up_after_five_collisions` |
| AC6 | A piece from `create_piece` | `send_to_event`, `place_hold`, `release_hold`, `return_to_warehouse` and `withdraw`, in that order | After each call, `public_code` read from the database is the same | `test_public_code_never_changes` |
| AC7 | Two pieces `reserved` / `event`, each with a hold past its expiry; the audit insert is forced to raise `RuntimeError` on its second call | `expire_holds` | It raises `RuntimeError`; the piece with the lower hold id is `available` / `event`, its hold is not active and it has one new record; the other piece is still `reserved` with an active hold and no new record | `test_expire_holds_isolates_each_hold` |
| AC8 | The finished work | `make check` | It passes, including "no missing migrations" and every test from spec 0002 | command output in the final report |

Reviewer checks, not tests:

- Migrating a database that already has two or more pieces gives each one a different valid code. The reviewer runs this; do not write a test for the migrations.
- Nothing writes `public_code` after the piece is created.
- Files were edited with the edit tool and commands were not chained (AGENTS.md section 4).
- No public name that this spec does not list.

## Out of scope

- QR labels, URLs, views, templates and any lookup of a piece by its code.
- Accepting codes typed in lower case or with look-alike characters.
- Django admin for these models.
- Catalog data (brand, category, size, condition, price) and any app other than `inventory`.
- Changing the states, the channels or any transition rule of spec 0002.
- Running `migrate` or changing the development database in any way.
- New dependencies, `AGENTS.md`, `opencode.jsonc`.
- Commits, unless the architect asks.

## Final report

As AGENTS.md section 7 requires: what changed, which commands ran with their results (including warnings), and what was not verified. Also list every acceptance criterion with the test that covers it. If a criterion is not covered, say so; do not claim it.
