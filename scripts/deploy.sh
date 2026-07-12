#!/usr/bin/env bash

set -Eeuo pipefail

SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_ROOT="${DEPLOY_ROOT:-$HOME/micro-production}"
MIROFISH_ENV_FILE="${MIROFISH_ENV_FILE:-$SOURCE_ROOT/.env}"
BACKEND_ENV="$DEPLOY_ROOT/.venv"
FRONTEND_ROOT="/var/www/micro-production"

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

for command in node npm uv rsync curl sudo; do
  command -v "$command" >/dev/null 2>&1 || fail "Required command not found: $command"
done

[[ -f "$MIROFISH_ENV_FILE" ]] || fail "Environment file not found: $MIROFISH_ENV_FILE"
[[ "$DEPLOY_ROOT" == "$HOME/"* ]] || fail "DEPLOY_ROOT must be inside $HOME"
[[ "$DEPLOY_ROOT" != "$SOURCE_ROOT" ]] || fail "DEPLOY_ROOT must differ from the source checkout"

printf 'Deploying %s to %s...\n' "${GITHUB_SHA:-local checkout}" "$DEPLOY_ROOT"
mkdir -p \
  "$DEPLOY_ROOT" \
  "$DEPLOY_ROOT/mirofish/backend/uploads" \
  "$DEPLOY_ROOT/mirofish/backend/logs"

rsync -a --delete \
  --exclude '/.git/' \
  --exclude '/.env' \
  --exclude '/.venv/' \
  --exclude '/.mirofish.pid' \
  --exclude '/frontend/node_modules/' \
  --exclude '/mirofish/node_modules/' \
  --exclude '/mirofish/frontend/node_modules/' \
  --exclude '/mirofish/backend/.venv/' \
  --exclude '/mirofish/backend/uploads/' \
  --exclude '/mirofish/backend/logs/' \
  "$SOURCE_ROOT/" "$DEPLOY_ROOT/"

ln -sfn "$MIROFISH_ENV_FILE" "$DEPLOY_ROOT/.env"

printf 'Installing and building the dashboard frontend...\n'
npm ci --prefix "$DEPLOY_ROOT/frontend"
npm run build --prefix "$DEPLOY_ROOT/frontend"
sudo mkdir -p "$FRONTEND_ROOT"
sudo rsync -a --delete "$DEPLOY_ROOT/frontend/dist/" "$FRONTEND_ROOT/"
sudo chown -R root:root "$FRONTEND_ROOT"

printf 'Syncing backend dependencies...\n'
UV_PROJECT_ENVIRONMENT="$BACKEND_ENV" \
  uv sync --project "$DEPLOY_ROOT/mirofish/backend" --frozen --no-dev

printf 'Restarting production services...\n'
sudo systemctl restart micro-backend.service
sudo nginx -t
sudo systemctl reload nginx.service

for _ in {1..30}; do
  if curl --fail --silent --show-error http://127.0.0.1:5001/health >/dev/null; then
    break
  fi
  sleep 1
done

curl --fail --silent --show-error http://127.0.0.1:5001/health >/dev/null \
  || fail "Backend health check failed"
curl --fail --silent --show-error http://127.0.0.1/ >/dev/null \
  || fail "Frontend health check failed"

printf 'Deployment complete: http://20.195.42.122\n'
