# Architect handoff

Last updated: 2026-11-12. Keep this file short and current; replace stale items instead of appending.

## How we work

- The architect designs an agentic workflow. A tester verifies behavior and the reports feed back to the agents.
- Build block by block. Validate each block before starting the next.
- Implementation: OpenCode v2 (2.2.7) with free models (for example `opencode/beam-free`). The Claude agent evaluates them and refines the configuration.

## State

Done and checked by the architect:

- Devcontainer: Python 3.13 and Node 22 dependencies baked into the image from the lockfiles. `doctor.sh` reports 29 passed, 0 failed.
- Django 5.2.19 skeleton on PostgreSQL 17. Settings read `DATABASE_URL`. The admin opens.
- Vite 8 + Tailwind 4 + django-vite work in dev mode. The home template renders.
- `make check` is green. pytest smoke tests and ruff are configured.
- `opencode.jsonc` blocks `uv` commands and edits to `uv.lock`.
- OpenCode loads AGENTS.md and answers questions about it correctly.
- One small task was run with `opencode/beam-free` (health endpoint).

Pending:

- Spike 2: domain core (states, atomic reservation, audit in the same transaction, concurrency test).
- Spike 3: real data import with quarantine.
- Restrict the Claude agent (`.claude/settings.json`) and check the limits actually hold in the VS Code extension.
- Design review (DRY, SOLID, KISS or whatever fits): first topics are where domain code lives and the single service for state transitions.
- Reconcile AGENTS.md section 6 with `docs/resumen-proyecto-vintage.md` sections 4 and 10. Known gaps: the state field is read-only in the admin and operators use explicit actions; JavaScript never holds business rules; `make check` should also run a typecheck (none is configured yet).
- Write the spec for the next block (given/when/then, acceptance criteria mapped to tests, explicit out-of-scope) in `docs/specs/`. Record design decisions in `docs/adr/`.
- Evaluate more OpenCode models with the protocol below.

## Decisions not already in AGENTS.md

- The detailed domain model lives in `docs/resumen-proyecto-vintage.md`: state and channel (section 4.1), manual transitions (4.2), holds (4.3), controls and audit (4.4), event mode (5), payments and closings (6), acceptance criteria for the tester (14). AGENTS.md section 6 is a shorter subset.
- A hold is one mechanism for every context. Bazaar transfers expire in minutes, configurable per event, and the piece returns to its previous state and channel. A future storefront cart holds about 15 minutes. The operator can extend a hold once, with a recorded reason.
- Admin is Django admin. Storefront and mobile event pages are server-rendered. A React/SPA admin, Django Ninja and a Flutter app come later.
- Payments: cash and bank transfer now. A webhook-based method is to be evaluated later.
- Printed QR labels on pieces are planned.
- First public site is a simple showcase. Bazaar and warehouse management come first, then the transition from GoTrendier.
- Spike plan has three pass/fail tests: pipeline (done), domain core and concurrency, real data import.

## Open decisions (the architect must confirm)

- Money as integer cents (what AGENTS.md says) or `Decimal`. The summary allows either.
- Where domain code lives. No apps layout exists yet; the health view ended up in `backend/config/`.

## Lessons learned

- OpenCode v2: the last matching rule wins. Invalid rules are dropped silently, so after editing `opencode.jsonc` check that `opencode debug config` still lists every rule. Do not use `--auto`.
- OpenCode v2 reads `AGENTS.md` only. The root file loads at session start. A nested `AGENTS.md` loads when the agent works in that directory.
- `opencode pair` prints a one-time link for the background service. Forward its port in VS Code (49374 was observed).
- Claude Code: `deny` beats `ask` beats `allow`, and specificity does not matter. `Edit` rules cover every editing tool. Bash rules are not a security boundary (`git -C . push` and `sh -c '...'` get past them). With a `CLAUDE.md` present, Claude reads it instead of `AGENTS.md`, which is why it imports `@AGENTS.md`.
- The VS Code extension has had reports of commands running without a prompt in manual mode. Test the limits after configuring them.
- Docker: a named volume is seeded from the image only on first creation. `post-create.sh` re-syncs `node_modules` using a lockfile hash stamp.

## Model evaluation protocol

Give every model the same small real task. Check each run:

1. Loads AGENTS.md: ask two detail questions without letting it read files.
2. Language: code, comments, tests and commits in English. Replies in Spanish.
3. Runs `make check` literally before declaring the task done.
4. No commit and no dependency, lockfile or `.devcontainer/` changes. Stops when a command is denied.
5. Final report separates what was verified from what was not.
6. Scope: does only what was asked.
7. Cost and behavior: tokens in and out, number of steps, retries after the same failure.

Rule changes come from observed failures, not from "just in case".

Results so far:

- `opencode/beam-free`, load test: correct answers, 9,713 tokens (5,161 in, 72 out, 192 reasoning, 4,288 cache).
- `opencode/beam-free`, health endpoint task: ran lint, check, migrations check, pytest and build separately instead of `make check`. Added an unrequested second route and test. Placed the view in `backend/config/` because AGENTS.md does not say where code lives. No commit, no dependency changes. Report was honest about what it did not verify.

Record future results in `docs/model-evaluations.md`.