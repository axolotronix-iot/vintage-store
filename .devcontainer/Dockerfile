# syntax=docker/dockerfile:1

# Build context is the repository root (see docker-compose.yml), so COPY paths
# below are relative to it.

# =============================================================================
# Block 1: base image
# =============================================================================
FROM node:22-bookworm-slim

ENV LANG=C.UTF-8

# =============================================================================
# Block 2: system packages
# ripgrep and jq are used by the agent's search and shell tools, so they are
# installed here instead of being downloaded at run time.
# psql and pg_isready are for debugging only. For dumps use
# `docker compose exec db pg_dump`: the bookworm client is older than the server.
# =============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    curl \
    make \
    openssh-client \
    postgresql-client \
    ripgrep \
    jq \
    less \
    procps \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Block 3: Python managed by uv
# The virtualenv lives outside the workspace, at /opt/venv, so the bind mount
# never hides it and stays free of thousands of small files.
# --no-cache keeps download caches out of the image layers.
# =============================================================================
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /usr/local/bin/

ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN uv python install 3.13 --no-cache

# =============================================================================
# Block 4: OpenCode 2.x
# npm installs four native variants of about 250 MB each. Only the glibc,
# AVX2 one is used on this image, so the musl variants and the baseline
# (no-AVX2) variants are removed in the same layer. If the host CPU has no AVX2
# (check: grep -c avx2 /proc/cpuinfo), drop the second pattern from the rm.
# The 2.x line (@opencode/cli) uses a different opencode.jsonc schema than the
# 1.x line (opencode-ai). Bump this version deliberately, never implicitly.
# =============================================================================
ARG OPENCODE_PACKAGE=@opencode/cli@2.2.7
RUN npm install -g --no-audit --no-fund --cache /tmp/npm-cache "${OPENCODE_PACKAGE}" \
    && cd "$(npm root -g)/@opencode/cli/node_modules/@opencode" \
    && rm -rf ./*-musl ./*-baseline* \
    && rm -rf /tmp/npm-cache \
    && opencode --version

# =============================================================================
# Block 5: mount points and ownership
# Everything that receives a volume or is written by the node user is created
# here, while it is still small, so chown never copies large trees into a new
# layer. A named volume inherits the ownership of its mount point in the image.
# =============================================================================
RUN mkdir -p \
        /home/node/.config/opencode \
        /home/node/.local/share/opencode \
        /home/node/.local/state/opencode \
        /home/node/.cache/uv \
        /home/node/.claude \
        /opt/venv \
        /workspace/frontend \
    && chown -R node:node /home/node /opt/venv /workspace

USER node

# =============================================================================
# Block 6: Python dependencies, exactly as pinned in uv.lock
# --locked fails the build if pyproject.toml and uv.lock disagree.
# =============================================================================
WORKDIR /tmp/backend-deps
COPY --chown=node:node backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-cache

# =============================================================================
# Block 7: frontend dependencies, exactly as pinned in package-lock.json
# The result is the seed of the node_modules named volume, which is mounted at
# /workspace/frontend/node_modules (the bind mount of /workspace would hide it
# otherwise). The stamp records which lockfile produced it; post-create.sh and
# doctor.sh compare it to detect a stale volume after a lockfile change.
# =============================================================================
WORKDIR /workspace/frontend
COPY --chown=node:node frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --cache /tmp/npm-cache \
    && sha256sum package-lock.json | cut -d' ' -f1 > node_modules/.lock-sha256 \
    && rm -rf /tmp/npm-cache

# =============================================================================
# Block 8: runtime
# =============================================================================
WORKDIR /workspace
CMD ["sleep", "infinity"]
