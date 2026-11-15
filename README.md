# vintage-store

Website and back-office for a vintage clothing business that sells unique pieces. About 70% of sales happen at physical bazaars; the site gives customers who cannot attend an online catalog, and gives the operator one place to manage inventory, bazaar sales and cash closings.

## Status

Built block by block. Done so far:

- Development environment (devcontainer) and the Django, Vite and Tailwind pipeline.
- `accounts`: custom user model.
- `inventory`: pieces with state and channel, holds with expiry, and one audited service for every transition.

Planned next: piece public code, catalog vocabularies, Excel import with quarantine, bazaar mode, storefront. See `docs/architect-handoff.md` for the current state.

## Stack

- Django 5.2 monolith with server-rendered templates and Django admin for the operator.
- PostgreSQL 17.
- Vite and Tailwind CSS as the asset pipeline (through django-vite).
- Everything runs inside a devcontainer. Exact versions are in `AGENTS.md`, section 2.

## Getting started

Requirements: Docker, VS Code and the Dev Containers extension.

1. Open the repository in VS Code and run **Dev Containers: Reopen in Container**.
2. Wait for the environment report at the end of the build. Every check must pass. Run it again at any time with `bash .devcontainer/doctor.sh`.
3. In the container terminal:

```bash
make migrate   # apply migrations
make back      # Django on :8000
make front     # Vite on :5173, in a second terminal
make check     # lint, Django checks, tests and build; run before every commit
```

`make help` lists every command.

## How we work

- `AGENTS.md` holds the rules for coding agents: commands, limits, conventions and domain rules.
- Each block has a spec in `docs/specs/`. Design decisions are recorded in `docs/adr/`.
- AI agents write the code from the spec. The architect reviews it and tests it by hand before it is merged.
- `docs/model-evaluations.md` records how each model performed on each block.

## Rebuilding the container

Rebuild after a change to `.devcontainer/` or to a lockfile (`backend/uv.lock`, `frontend/package-lock.json`).

What survives a rebuild, because it lives in named volumes:

- the development database (`pgdata`);
- OpenCode login and sessions;
- Claude Code login, settings and session history (`claude_config`);
- `node_modules` and the uv cache.

Everything else in the container home directory and in `/tmp` is discarded.

Steps:

1. Commit your work.
2. From the host, in the repository root, build the image first. If this fails, the running container is untouched:

   ```bash
   docker compose -f .devcontainer/docker-compose.yml build workspace
   ```

3. In VS Code run **Dev Containers: Rebuild Container**.
4. In the new container, check the environment:

   ```bash
   bash .devcontainer/doctor.sh
   make check
   ```

Never run `docker compose down -v` and never delete the volumes: that erases the database and the logins.

### Adding a Python dependency

Only the architect changes dependencies.

```bash
cd backend && uv add <package>
```

Commit `backend/pyproject.toml` and `backend/uv.lock`, then rebuild. The image installs exactly what `uv.lock` pins; the Dockerfile does not list packages.

### Restoring Claude Code state from a backup

Only needed when the `claude_config` volume is new or was deleted. Run these on the host. Find the container id with `docker ps`.

Before the rebuild:

```bash
docker cp <container>:/home/node/.claude ~/claude-backup
docker cp <container>:/home/node/.claude.json ~/claude-backup.json
```

After the rebuild, with the id of the new container:

```bash
docker cp ~/claude-backup/. <container>:/home/node/.claude/
docker cp ~/claude-backup.json <container>:/home/node/.claude/.claude.json
docker exec -u root <container> chown -R node:node /home/node/.claude
```

Then reload the VS Code window. The backup contains credentials: keep it outside the repository and delete it once Claude Code works.
