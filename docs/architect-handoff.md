# Architect handoff

Last updated: 2026-11-15. Keep this file short and current; replace stale items instead of appending.

## How we work

- The architect designs an agentic workflow. A tester verifies behavior and the reports feed back to the agents.
- Build block by block. Validate each block before starting the next.
- The spikes measure the agentic workflow, but their code is kept: this workspace evolves into the full application. Each spike is a normal block with a spec and the full definition of done.
- One git branch per attempt, created by the architect from the same base commit. It merges into main only if the block passes the architect's review and the tester. A failed attempt is discarded.
- Implementation: OpenCode v2 (2.2.7) with free models (for example `opencode/beam-free`). The Claude agent evaluates them and refines the configuration.

## State

Done and checked by the architect:

- Devcontainer: Python 3.13 and Node 22 dependencies baked into the image from the lockfiles. `doctor.sh` reports 29 passed, 0 failed.
- Django 5.2.19 skeleton on PostgreSQL 17. Settings read `DATABASE_URL`. The admin opens.
- Vite 8 + Tailwind 4 + django-vite work in dev mode. The home template renders.
- `make check` is green. pytest smoke tests and ruff are configured.
- `opencode.jsonc` blocks `uv` commands and edits to `uv.lock`.
- OpenCode loads AGENTS.md and answers questions about it correctly.
- One small task was run with `opencode/beam-free` (health endpoint). Its code was removed afterwards.
- `accounts` app with the custom user (spec 0001, ADR 0001), written by `opencode/beam-free`, merged into main. The development database was recreated and migrated with it.
- Spike 2: `inventory` app (spec 0002 revision 2), written by `opencode/beam-free` on `inventory-attempt-2`, merged into main after one correction pass and the architect's manual test. The development database has `inventory.0001_initial` and one test piece, which the audit protects from deletion. Attempt 1 is kept on `inventory-attempt-1`.

Pending:

- Rebuild the container (steps in `README.md`). The compose file now has a `claude_config` volume and `CLAUDE_CONFIG_DIR`, and `uv.lock` has openpyxl 3.1.5. After the rebuild restore the Claude Code backup, then check `doctor.sh`, `make check`, the OpenCode sessions and that Claude Code keeps its login.
- Spike 3, block A: run `docs/specs/0003-piece-public-code.md` with OpenCode on branch `public-code-attempt-1`, in a new session. It also closes the three review findings of spec 0002 and measures whether `beam-free` obeys the two new rules in AGENTS.md section 4 (no file edits from the shell, no chained commands).
- Spike 3, block B (spec 0004, not written): `catalog` app with vocabularies (brand with aliases, category, size, condition enum) and the piece details, one-to-one with the piece, with the list price in cents.
- Spike 3, block C (spec 0005, not written): `.xlsx` importer with quarantine. One batch per file and one record per row, imported or quarantined; a management command prints the totals and the quarantine rate.
- Spike 3, step D: measure with the real sample. The customer has not delivered it yet. The real file stays out of git and no OpenCode agent reads it.
- Run the three block tests in Claude Code (`uv --version`, edit `uv.lock`, `git push`) and check the Manual mode indicator in the VS Code extension.
- Remove the stray user-level `ask` rule that only says "CLAUDE.md".
- Decide whether `Edit(/backend/**)` and `Edit(/frontend/src/**)` go in `ask` in `.claude/settings.json` to enforce the product-code limit.
- Translate the Spanish comments in `opencode.jsonc` and the `make help` strings in the Makefile to English.
- `make check` has no typecheck yet; the project summary (section 10) expects one.
- Write the spec for the next block (given/when/then, acceptance criteria mapped to tests, explicit out-of-scope) in `docs/specs/`. Record design decisions in `docs/adr/`.
- Evaluate more OpenCode models with the protocol below.

## Decisions not already in AGENTS.md

- The detailed domain model lives in `docs/resumen-proyecto-vintage.md`: state and channel (section 4.1), manual transitions (4.2), holds (4.3), controls and audit (4.4), event mode (5), payments and closings (6), acceptance criteria for the tester (14). AGENTS.md section 6 is a shorter subset.
- A hold is one mechanism for every context. Bazaar transfers expire in minutes, configurable per event, and the piece returns to its previous state and channel. A future storefront cart holds about 15 minutes. The operator can extend a hold once, with a recorded reason.
- Admin is Django admin. Storefront and mobile event pages are server-rendered. A React/SPA admin, Django Ninja and a Flutter app come later.
- Payments: cash and bank transfer now. A webhook-based method is to be evaluated later.
- Printed QR labels on pieces are planned.
- First public site is a simple showcase. Bazaar and warehouse management come first, then the transition from GoTrendier.
- Spike plan has three pass/fail tests: pipeline (done), domain core and concurrency (done), real data import.
- Domain code layout is recorded in `docs/adr/0001-domain-code-layout.md`.
- Piece public code: 6 random characters, recorded in `docs/adr/0002-piece-public-code.md`.
- Spike 3 decisions (2026-11-15): catalog data lives in a new `catalog` app that depends on `inventory`; the importer reads `.xlsx` with openpyxl; the blocks are built with synthetic data until the real sample arrives.
- One new OpenCode session per block and per attempt, because the root AGENTS.md loads only at session start. The same session is used only for the correction pass of that attempt.

## Open decisions (the architect must confirm)

- Late payment on the storefront. The summary contradicts itself: section 4.3 rejects a payment that arrives after the hold expired until the operator reactivates the hold; section 8 sells the piece if it is still free and refunds otherwise. AGENTS.md scopes the 4.3 rule to bazaar transfer holds until this is decided.
- How to model a piece that is "migrating" from GoTrendier (summary section 14: it must not appear as purchasable anywhere). It is none of the four states or four channels.

## Lessons learned

- OpenCode v2: the last matching rule wins. Invalid rules are dropped silently, so after editing `opencode.jsonc` check that `opencode debug config` still lists every rule. Do not use `--auto`.
- OpenCode v2 reads `AGENTS.md` only. The root file loads at session start. A nested `AGENTS.md` loads when the agent works in that directory.
- `opencode pair` prints a one-time link for the background service. Forward its port in VS Code (49374 was observed).
- Claude Code: `deny` beats `ask` beats `allow`, and specificity does not matter. `Edit` rules cover every editing tool. Bash rules are not a security boundary (`git -C . push` and `sh -c '...'` get past them). With a `CLAUDE.md` present, Claude reads it instead of `AGENTS.md`, which is why it imports `@AGENTS.md`.
- The VS Code extension has had reports of commands running without a prompt in manual mode. Test the limits after configuring them.
- The OpenCode background service requests `GET /health` on port 8000 about once a minute (observed 2026-11-14). The 404 lines in the dev server log come from it, not from project code. The cause was not investigated.
- Specs must name the public functions, models, fields and tests. When names were left open, `beam-free` accepted any argument order and added aliases for "hidden tests".
- OpenCode asks for approval on every chained command (`cd x && pytest`), even when the command itself is allowed. `beam-free` chains almost everything.
- A correction pass can cost more than the implementation: on spec 0002, four small fixes took 46 steps against 36. Send review findings as a numbered list with the expected result of each one, and re-review the whole diff afterwards, because `beam-free` broke two unrelated tests with a scripted replace.
- One new OpenCode session per attempt. For cumulative tokens and steps use `opencode session list` and `opencode session export <id>`; the session panel shows only the last request.
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

Later results are in `docs/model-evaluations.md`. A spec with an explicit out-of-scope section kept `beam-free` inside the scope on spec 0001.