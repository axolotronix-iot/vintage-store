#!/usr/bin/env bash
# Runs once after the container is created. Dependencies are already in the
# image; this script only makes sure the environment still matches the
# lockfiles (for example after a lockfile changed but the volume did not), then
# prints the doctor report. Safe to run again.
set -euo pipefail

cd /workspace

# The bind mount may be owned by a different uid than the container user.
if ! git config --global --get-all safe.directory | grep -qx /workspace; then
  git config --global --add safe.directory /workspace
fi

if [ -f backend/uv.lock ]; then
  echo "--- backend: checking the virtualenv against uv.lock"
  (cd backend && uv sync --locked)
else
  echo "warning: backend/uv.lock is missing; run 'uv lock' in backend/ and commit it"
fi

if [ -f frontend/package-lock.json ]; then
  want=$(sha256sum frontend/package-lock.json | cut -d' ' -f1)
  have=$(cat frontend/node_modules/.lock-sha256 2>/dev/null || true)
  if [ "$want" != "$have" ]; then
    echo "--- frontend: node_modules does not match package-lock.json, reinstalling"
    (
      cd frontend
      # node_modules is a volume mount point: empty it instead of removing it,
      # which is why this uses npm install and not npm ci.
      find node_modules -mindepth 1 -delete
      npm install --no-audit --no-fund
      printf '%s\n' "$want" > node_modules/.lock-sha256
    )
  else
    echo "--- frontend: node_modules matches package-lock.json"
  fi
else
  echo "warning: frontend/package-lock.json is missing; run 'npm install' in frontend/ and commit it"
fi

echo "--- environment report"
bash .devcontainer/doctor.sh || true
