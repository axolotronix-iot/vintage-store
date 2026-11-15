# AGENTS.md

## 1. Project

Website and back-office for a vintage clothing business. Every piece is unique (one unit, never a stock count). About 70% of sales happen at physical bazaars; online sales currently go through GoTrendier and will be migrated here.

First goal: the foundations for warehouse management, bazaar sales, a product catalog, a simple public storefront (showcase) and a simple admin (Django admin). The customer keeps inventory in Excel and notebooks today, so importing that data is part of the application.

Architecture: Django 5.2 monolith, server-rendered templates, PostgreSQL 17. Vite + Tailwind are only an asset pipeline (via django-vite).

Out of scope for now: online checkout and payment webhooks, a mobile app, an API layer (Django Ninja), a React/SPA admin. Do not start any of them.

## 2. Environment and commands

Runs inside the devcontainer (`.devcontainer/`): a `workspace` service (node user) plus a `db` service (`postgres:17`). `DATABASE_URL` is set by `docker-compose.yml` and is required by `settings.py`.

Versions (installed in the container):

| Tool | Version |
|---|---|
| Python | 3.13.18 (`requires-python >=3.13,<3.14`, managed by uv 0.13.7, venv at `/opt/venv`) |
| Node / npm | 22.23.4 / 10.9.9 |
| Django | 5.2.19 |
| psycopg | 3.3.8 |
| django-vite | 3.2.0 |
| pytest / pytest-django | 9.2.0 / 4.14.0 |
| ruff | 0.17.4 |
| Vite / Tailwind CSS | 8.3.8 / 4.3.5 |
| PostgreSQL | 17 (image tag `postgres:17`) |

- The virtualenv (`/opt/venv`) is on PATH: use `python`, `pytest` and `ruff` directly. Do not use `uv run` (denied).
- Django management commands run from `backend/` (for example `cd backend && python manage.py check`).
- Tests need the `db` service running: pytest-django creates a `test_vintage` database in PostgreSQL.

Commands (run from the repository root):

| Command | What it does | Status |
|---|---|---|
| `make lint` | `ruff check` + `ruff format --check` in `backend/` (no file changes) | verified |
| `make test` | `pytest` in `backend/` | verified |
| `make build` | `vite build` into `backend/frontend_dist/` | verified |
| `make fmt` | `ruff check --fix` + `ruff format` (modifies files) | verified |
| `make check` | lint, `manage.py check`, `makemigrations --check --dry-run`, test, build. Run before every commit | verified |
| `make migrate` | `manage.py migrate` | verified |
| `make back` | Django dev server on `0.0.0.0:8000` | verified |
| `make front` | Vite dev server on `:5173` | verified |

## 3. Repository structure

```
.
├── Makefile                # Project commands
├── opencode.jsonc          # OpenCode permission rules
├── AGENTS.md               # Instructions for coding agents
├── docs/                   # Project summary (Spanish), architect handoff, specs/ and adr/ (as they are written)
├── .gitignore / .dockerignore  # Ignore rules for git and Docker builds
├── .devcontainer/          # Container image, compose (workspace + db), post-create and doctor scripts
├── backend/                # Django project (pyproject.toml, uv.lock, manage.py)
│   ├── config/             # Django settings, URLs, WSGI/ASGI
│   ├── accounts/           # Custom user model (AUTH_USER_MODEL = "accounts.User")
│   ├── templates/          # Project-level Django templates (base.html, home.html)
│   ├── tests/              # pytest test suite
│   └── frontend_dist/      # Vite build output read by django-vite (generated, git-ignored)
└── frontend/               # Vite + Tailwind sources (package.json, vite.config.js)
    └── src/                # JS/CSS entry points (main.js, style.css)
```

### Backend layout rules

Decided in `docs/adr/0001-domain-code-layout.md`.

- Domain code lives in Django apps under `backend/`: `accounts` (custom user) and `inventory` (piece, hold, audit, transitions). Do not create another app unless the spec of the block says so.
- `inventory/services.py` is the only code that writes piece state, piece channel, holds or audit records. Views, admin, management commands and imports call it.
- Other apps may read `inventory` models but never write them. `inventory` never imports an app that depends on it.
- Refer to the user with `settings.AUTH_USER_MODEL` or `get_user_model()`. Never import `django.contrib.auth.models.User`.
- Tests go in `backend/tests/<app>/`. Every test directory has an `__init__.py`.

## 4. Working limits

These limits are enforced by OpenCode through `opencode.jsonc`. Other agents (for example Claude Code) do not read that file: follow the limits anyway.

From `opencode.jsonc`:

- **Dependencies:** never add, remove or update them. `uv`, `pip`, `pip3`, `python -m pip`, `npm install/i/ci/uninstall/update` are denied. Only the architect changes dependencies (lockfile + image rebuild).
- **Protected files (no edits):** `.devcontainer/*`, `uv.lock`, `package-lock.json`, `.git/*`, `.env`.
- **Edit only with approval:** `AGENTS.md`, `opencode.jsonc`.
- **Git:** `status`, `diff`, `log`, `show` are allowed. `add` and `commit` require approval. `push`, `reset`, `clean`, `rebase`, `branch -D` and `config` are denied. Work on the current branch: the architect creates one branch per attempt. Never create or switch branches.
- **Shell:** anything not explicitly allowed asks first. Allowed: `ls`, `pwd`, `rg`, `make test/lint/fmt/check/build`, `pytest`, `ruff`, `python manage.py check`, `python manage.py makemigrations`, `npm run build`. `sudo` is denied.
- **Outside the project:** access to external directories requires approval.

## 5. Language and conventions

- The user talks to agents in Spanish. Reply to the user in Spanish.
- Everything written into the repository is in English: code, identifiers, comments, docstrings, test names, commit messages and AGENTS.md itself.
- Exception: text shown to customers or operators (templates, admin labels, messages) is Spanish (es-MX).

## 6. Domain rules

These rules are intent: some have no code yet. When you implement or touch one, add a test for it (see section 7).

- The detailed domain model is in `docs/resumen-proyecto-vintage.md`, sections 4 to 6 (Spanish). Read them before touching domain code. If they conflict with this file, this file wins.
- Each block has a spec in `docs/specs/`. The spec of the block in progress is binding, including its out-of-scope section: build nothing it lists as out of scope. If the spec conflicts with this file, stop and report.

### Inventory

- A piece is unique. Never model quantity or stock counts.
- A piece has a public code: short, unique, assigned at creation, never changed or reused. URLs, QR labels and messages use it, never the database id.
- A piece is offered in exactly one channel at a time: warehouse, event, website or GoTrendier. While a piece is assigned to an event it does not accept online reservations and is not shown as purchasable online.
- Piece states are: available, reserved, sold, withdrawn. Do not invent other states or channels without asking.
- A hold (reservation) has an expiry. When it expires, the piece returns to the state and channel it had before the hold, not blindly to "available".
- A hold is one mechanism for every context. For bazaar transfers its duration is configured per event.
- An operator can extend a hold once, with a recorded reason. A second extension is rejected.
- Expired holds are released by a management command. Every service operation also treats a hold past its expiry as expired, even if the command has not run.
- For bazaar transfer holds, a payment confirmation that arrives after the hold expired is rejected until an operator reactivates the hold. Reactivating a hold is rejected if the piece was sold to someone else.
- State and channel changes must be atomic in PostgreSQL: use a conditional `UPDATE ... WHERE state = <expected>` and check the affected row count. Never read-then-write in Python. Two simultaneous attempts on the same piece: exactly one succeeds.
- Every state or channel change writes an audit record (who, when, from, to, reason) in the same transaction. If the audit write fails, the change rolls back.
- All transitions go through one domain service. Views, admin actions, imports and management commands never set state directly. Manual changes by operators (for example withdrawing a piece) use the same service and the same audit.

### Manual actions and admin

- Every transition requires a reason and is rejected without one. Automatic transitions (for example hold expiry) record a system reason and no user.
- Withdrawing a piece, recording a sale made outside the platform, reactivating a hold, and returning a withdrawn piece to available each require their own permission. Returning a withdrawn piece is only for data-entry errors and needs supervisor permission.
- An action that affects a buyer with an active hold or a pending payment requires a two-step confirmation.
- In Django admin the state and channel fields are read-only. Operators change them only through explicit actions that call the domain service.

### Money and payments

- Never use floats for money. Store amounts as integer cents (MXN).
- Keep the list price and the charged price as separate values. A discount is recorded explicitly, with the reason for the difference; never overwrite the list price.
- Payment methods: cash and bank transfer. A transfer counts as paid only after it is confirmed against the bank statement; until then the piece stays reserved. Confirming the same payment twice must have no additional effect (idempotent). A webhook-based method is future work.
- Cash payments are created confirmed; transfers are created pending. A pending transfer does not count in a closing until it is confirmed.

### Time and cash closings

- Store datetimes in UTC (`USE_TZ = True`). Day boundaries for cash closings use `America/Mexico_City`.
- A confirmed closing is immutable: never edit or delete it. Corrections are recorded as new entries.
- Money movements are never edited. A correction is a new movement that references the original.
- A cash closing records the difference between counted and expected cash, with a reason. A difference is never corrected silently.

### Catalog data

- Use controlled vocabularies (tables or enums), not free text: category, size, condition and similar. Brand is its own entity with aliases. Condition is an enum.
- When importing external data (GoTrendier, Excel), invalid or ambiguous rows go to a quarantine for human review. Never silently fix or drop them.

### Security and boundaries

- Permissions are enforced in the backend. Hiding something in the UI is not a permission check.
- Never put personal data, tokens or secrets in rendered HTML or in committed files.
- Pages are server-rendered Django templates. Domain logic lives in the backend domain layer, not in templates or JavaScript.

## 7. Definition of done

A task is done only when all of this is true:

- `make check` passes (lint, Django check, no missing migrations, tests, build). Run it; do not assume it passes.
- Every domain rule you touched has a test that fails without your change.
- Code that decides who wins a race has a concurrency test.
- Migrations are committed and the database is never changed by hand.
- No dependency, lockfile or `.devcontainer/` change. If the task needs one, stop and say so.
- Commit only when the user asks. Commit messages are in English.
- The final report says what changed, which commands you ran with their results, and what you did not verify.

## 8. When to ask

Ask before:

- changing the state or channel model, the money representation, or how closings work;
- adding a state, channel or payment method;
- deleting data or changing a migration that is already applied;
- anything that needs a new dependency;
- doing more than the task asked.

Do not ask about naming, file placement inside the existing structure, test design or formatting.

Stop and report instead of choosing when:

- the task conflicts with a rule in this file;
- a command is denied by the permissions: do not work around it with another tool or script;
- the same command fails twice with the same error: do not retry with variations.
