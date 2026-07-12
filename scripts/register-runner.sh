#!/usr/bin/env bash

set -Eeuo pipefail

REPOSITORY="${GITHUB_REPOSITORY:-GenyoNguyen/one-week-stand}"
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner-micro}"
RUNNER_NAME="${RUNNER_NAME:-$(hostname)}"
RUNNER_LABEL="${RUNNER_LABEL:-micro-production}"
ARCHIVE="$(mktemp --suffix=.tar.gz)"

cleanup() {
  rm -f "$ARCHIVE"
}
trap cleanup EXIT

for command in curl gh python3 sha256sum tar sudo; do
  command -v "$command" >/dev/null 2>&1 || {
    printf 'Error: required command not found: %s\n' "$command" >&2
    exit 1
  }
done

[[ ! -e "$RUNNER_DIR/.runner" ]] || {
  printf 'Error: a runner is already configured in %s\n' "$RUNNER_DIR" >&2
  exit 1
}

release_json="$(gh api repos/actions/runner/releases/latest)"
asset_name="$(python3 -c '
import json, sys
release = json.load(sys.stdin)
print(next(asset["name"] for asset in release["assets"] if asset["name"].endswith("linux-x64-" + release["tag_name"].removeprefix("v") + ".tar.gz")))
' <<<"$release_json")"
asset_url="$(python3 -c '
import json, sys
release = json.load(sys.stdin)
name = sys.argv[1]
print(next(asset["browser_download_url"] for asset in release["assets"] if asset["name"] == name))
' "$asset_name" <<<"$release_json")"
asset_digest="$(python3 -c '
import json, sys
release = json.load(sys.stdin)
name = sys.argv[1]
print(next(asset["digest"] for asset in release["assets"] if asset["name"] == name).removeprefix("sha256:"))
' "$asset_name" <<<"$release_json")"

printf 'Downloading and verifying %s...\n' "$asset_name"
curl --fail --location --retry 3 --output "$ARCHIVE" "$asset_url"
printf '%s  %s\n' "$asset_digest" "$ARCHIVE" | sha256sum --check --status

mkdir -p "$RUNNER_DIR"
tar -xzf "$ARCHIVE" -C "$RUNNER_DIR"

registration_token="$(
  gh api --method POST "repos/$REPOSITORY/actions/runners/registration-token" --jq .token
)"

printf 'Registering %s for %s...\n' "$RUNNER_NAME" "$REPOSITORY"
(
  cd "$RUNNER_DIR"
  ./config.sh \
    --unattended \
    --replace \
    --url "https://github.com/$REPOSITORY" \
    --token "$registration_token" \
    --name "$RUNNER_NAME" \
    --labels "$RUNNER_LABEL" \
    --work _work
  sudo ./svc.sh install "$USER"
  sudo ./svc.sh start
)

printf 'Runner registered and started.\n'
