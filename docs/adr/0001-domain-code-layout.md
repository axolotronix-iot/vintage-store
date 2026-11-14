# ADR 0001: Domain code layout

Status: accepted (2026-11-14)

## Context

The spikes measure the agentic workflow, but their code is kept: this repository evolves into the full application. Decisions that are expensive to reverse in Django (which app owns a model, the user model) must be made before the first domain migration. Decisions that are cheap to add later (new apps, new fields) wait for the block that needs them.

AGENTS.md section 6 requires atomic state and channel changes, an audit record in the same transaction, and one domain service for every transition.

## Decision

- Domain code lives in Django apps under `backend/`. Two apps exist before Spike 2: `accounts` and `inventory`.
- `accounts` holds a custom user model with no extra fields. `AUTH_USER_MODEL` points to it from the first domain migration.
- `inventory` owns the piece (state and channel), the hold and the transition audit record. They change together in one transaction, so they live together.
- `inventory/services.py` is the single transition service and the public interface of the app. One private function performs the conditional `UPDATE` and the audit insert in the same transaction; every public operation goes through it.
- Other apps may read `inventory` models (foreign keys, queries). Only `inventory/services.py` writes state, channel, holds or audit records.
- Dependencies point one way: `inventory` never imports an app that depends on it. A hold receives its expiry as a parameter, so `inventory` does not need to know about events.
- Expired holds are released by a management command. The service also treats a hold past its expiry as expired when the command has not run yet.
- Other apps (`catalog`, `events`, `payments`) are created by the block that needs them, not before.
- Tests stay in `backend/tests/<app>/`.

## Consequences

- Switching `AUTH_USER_MODEL` requires recreating the development database once, before Spike 2. Only the architect does that.
- `inventory/services.py` will grow. When it becomes hard to navigate it turns into a package that keeps the same public names.
- The boundary between apps is checked in review with `rg`, not by a tool. An import linter would be a new dependency and is deferred.
- Payments and cash closings will keep their own immutable records; they do not reuse the piece audit table.

## Alternatives rejected

- Four apps now (`inventory`, `catalog`, `events`, `payments`): three empty apps with guessed boundaries, and agents tend to fill them.
- Small apps per concept (`pieces`, `holds`, generic `audit`): a hold cannot exist without changing the piece and writing the audit, so the apps would import each other and the single service would be split. A generic audit has no second user today.
