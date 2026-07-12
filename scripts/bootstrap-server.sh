#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_ROOT="/home/tcuong1000/micro-production"
SOURCE_ENV="$ROOT_DIR/mirofish/backend/.venv"
PRODUCTION_ENV="$DEPLOY_ROOT/.venv"

command -v sudo >/dev/null 2>&1 || {
  printf 'Error: sudo is required\n' >&2
  exit 1
}

mkdir -p "$DEPLOY_ROOT"
if [[ -d "$SOURCE_ENV" && ! -L "$SOURCE_ENV" && ! -e "$PRODUCTION_ENV" ]]; then
  printf 'Moving the existing backend environment to %s...\n' "$PRODUCTION_ENV"
  mv "$SOURCE_ENV" "$PRODUCTION_ENV"
  ln -s "$PRODUCTION_ENV" "$SOURCE_ENV"
fi

printf 'Installing Nginx and production service definitions...\n'
sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y nginx
sudo install -m 0644 "$ROOT_DIR/deploy/micro-backend.service" \
  /etc/systemd/system/micro-backend.service
sudo install -m 0644 "$ROOT_DIR/deploy/nginx.conf" \
  /etc/nginx/sites-available/micro-production
sudo ln -sfn /etc/nginx/sites-available/micro-production \
  /etc/nginx/sites-enabled/micro-production
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl daemon-reload
sudo systemctl enable nginx.service micro-backend.service
sudo nginx -t

printf 'Server bootstrap complete. Run ./scripts/deploy.sh to deploy.\n'
