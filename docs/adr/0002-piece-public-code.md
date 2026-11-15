# ADR 0002: Piece public code

Status: accepted (2026-11-15)

## Context

AGENTS.md section 6 requires a public code for every piece: short, unique, assigned at creation, never changed or reused. URLs, QR labels and messages use it instead of the database id. The format was open. The Excel import (Spike 3) creates pieces, so the code must exist before it.

Operators will read the code from a label, write it by hand and dictate it at a bazaar.

## Decision

- The code is 6 characters drawn at random from `23456789ABCDEFGHJKMNPQRSTVWXYZ`: digits and capital letters without `0`, `1`, `I`, `L`, `O` and `U`. That is 30 symbols and about 729 million codes.
- The code lives in `Piece.public_code` in the `inventory` app, because it is the identity of the piece.
- The field has a default that generates a code, so a piece gets one however it is created. The database enforces uniqueness with a unique constraint.
- `inventory.services.create_piece` generates the code itself and retries with a new one when the database reports a collision, up to 5 attempts.
- The code is never updated. A piece with audit records cannot be deleted (spec 0002), so a code is never reused.

## Consequences

- A code does not reveal how many pieces exist and the next one cannot be guessed.
- A random code is harder to dictate than a number. Six characters without look-alike symbols keeps that cost low.
- Existing pieces get their code in a data migration. Adding a unique field to a table with rows takes three migrations (add nullable, fill, make unique), as the Django documentation describes.
- Immutability is a convention checked in review, not a database trigger.
- Accepting a mistyped code (lower case, `O` typed for `0`) is the job of the lookup that arrives with the QR block, not of this decision.

## Alternatives rejected

- Sequential code with a prefix (`VT-000123`): easy to dictate, but it reveals the sales volume and makes URLs guessable.
- Keeping `0` and `1`: two more symbols, and the handwriting mistakes come back.
- UUID: unique without retries, but nobody can read it from a label.
- Deferring the code until the QR block: imported pieces would exist without a code, against "assigned at creation".
