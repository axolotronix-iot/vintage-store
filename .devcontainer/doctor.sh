#!/usr/bin/env bash
# Environment check. Run it by hand after building the container, before
# starting the agent. Prints PASS, WARN or FAIL per item and exits with 1 when
# anything failed.
set -u

WORKSPACE="${WORKSPACE:-/workspace}"
VENV_DIR="${UV_PROJECT_ENVIRONMENT:-/opt/venv}"
PY="$VENV_DIR/bin/python"
pass=0
warn=0
fail=0

ok() {
  printf '  PASS  %s%s\n' "$1" "${2:+: $2}"
  pass=$((pass + 1))
}

bad() {
  printf '  FAIL  %s\n        %s\n' "$1" "$2"
  fail=$((fail + 1))
}

note() {
  printf '  WARN  %s\n        %s\n' "$1" "$2"
  warn=$((warn + 1))
}

# check LABEL HINT COMMAND...  -> PASS shows the first output line.
check() {
  local label="$1" hint="$2" out
  shift 2
  if out=$("$@" 2>&1); then
    ok "$label" "$(printf '%s' "$out" | head -n 1)"
  else
    bad "$label" "$hint"
  fi
}

writable() {
  local f="$1/.doctor.$$"
  touch "$f" 2>/dev/null && rm -f "$f"
}

node_version() {
  node -e 'const [a, b] = process.versions.node.split(".").map(Number);
           if (a > 22 || (a === 22 && b >= 12)) { console.log(process.versions.node); process.exit(0); }
           console.error("node " + process.versions.node + " is older than 22.12"); process.exit(1);'
}

python_version() {
  "$PY" -c 'import sys; assert sys.version_info[:2] == (3, 13), sys.version; print(sys.version.split()[0])'
}

opencode_version() {
  local v
  v=$(opencode --version) || return 1
  case "$v" in
    *v2.*) printf '%s\n' "$v" ;;
    *) printf 'expected a 2.x release, got: %s\n' "$v" >&2; return 1 ;;
  esac
}

package_version() {
  node -p "require('$WORKSPACE/frontend/node_modules/$1/package.json').version"
}

python_env_in_sync() {
  (cd "$WORKSPACE/backend" && uv sync --locked --check 2>&1 | tail -n 1)
}

node_modules_in_sync() {
  local want have
  want=$(sha256sum "$WORKSPACE/frontend/package-lock.json" | cut -d' ' -f1) || return 1
  have=$(cat "$WORKSPACE/frontend/node_modules/.lock-sha256" 2>/dev/null) || {
    echo "no stamp found in node_modules" >&2
    return 1
  }
  if [ "$want" != "$have" ]; then
    echo "package-lock.json changed since node_modules was installed" >&2
    return 1
  fi
  echo "matches package-lock.json"
}

db_query() {
  "$PY" -c 'import os, psycopg
with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as c:
    print(c.execute("select current_database(), current_user").fetchone())'
}

echo "== user and permissions"
check "not running as root" "remoteUser must be node" bash -c '[ "$(id -u)" -ne 0 ] && id -un'
for dir in \
  "$WORKSPACE" \
  "$VENV_DIR" \
  "$WORKSPACE/frontend/node_modules" \
  "$HOME/.cache/uv" \
  "$HOME/.config/opencode" \
  "$HOME/.local/share/opencode" \
  "$HOME/.local/state/opencode"; do
  check "writable $dir" "wrong owner: recreate the volume (docker volume rm) and rebuild" writable "$dir"
done

echo "== tools"
check "node (needs >= 22.12 for Vite)" "wrong base image" node_version
check "npm" "missing" npm --version
check "uv" "missing" uv --version
check "python 3.13 in the virtualenv" "run: cd backend && uv sync" python_version
check "opencode 2.x" "reinstall with the OPENCODE_PACKAGE build argument" opencode_version
check "ripgrep" "missing" rg --version
check "git" "missing" git --version

echo "== backend dependencies"
check "django" "run: cd backend && uv sync" "$PY" -c 'import django; print(django.get_version())'
check "psycopg" "run: cd backend && uv sync" "$PY" -c 'import psycopg; print(psycopg.__version__)'
check "django-vite" "run: cd backend && uv sync" "$PY" -c 'import django_vite; print("importable")'
check "pytest" "run: cd backend && uv sync" "$VENV_DIR/bin/pytest" --version
check "ruff" "run: cd backend && uv sync" "$VENV_DIR/bin/ruff" --version
check "virtualenv matches uv.lock" "run: cd backend && uv sync --locked" python_env_in_sync

echo "== frontend dependencies"
check "vite" "run: cd frontend && npm install" "$WORKSPACE/frontend/node_modules/.bin/vite" --version
check "tailwindcss" "run: cd frontend && npm install" package_version tailwindcss
check "@tailwindcss/vite" "run: cd frontend && npm install" package_version @tailwindcss/vite
check "node_modules matches package-lock.json" "re-run: bash .devcontainer/post-create.sh" node_modules_in_sync

echo "== database"
check "DATABASE_URL is set" "set it in docker-compose.yml" bash -c '[ -n "${DATABASE_URL:-}" ] && echo set'
check "server accepts connections" "is the db service healthy? check docker compose ps" pg_isready -d "${DATABASE_URL:-postgres://db}"
check "login and query with psycopg" "credentials or driver problem" db_query

echo "== repository and network"
if git -C "$WORKSPACE" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ok "git repository"
else
  note "git repository" "not initialised yet: run git init at the repository root"
fi
if curl -fsS -o /dev/null --max-time 8 https://opencode.ai 2>/dev/null; then
  ok "can reach opencode.ai"
else
  note "can reach opencode.ai" "could not reach it (no network, or blocked): the agent will not reach its model provider"
fi

printf '\n%d passed, %d warnings, %d failed\n' "$pass" "$warn" "$fail"
[ "$fail" -eq 0 ]
