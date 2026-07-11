#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MIROFISH_DIR="$ROOT_DIR/mirofish"
PID_FILE="$ROOT_DIR/.mirofish.pid"
SETUP_ONLY=false
SKIP_INSTALL=false
STOP_ONLY=false
CHILD_PID=""

usage() {
  cat <<'EOF'
Usage: ./run.sh [options]

Options:
  --setup-only   Install dependencies without starting the services
  --skip-install Restart immediately with the installed dependencies
  --stop         Stop the running MiroFish services and exit
  -h, --help     Show this help message

Set FORCE_INSTALL=1 to reinstall dependencies even when lockfiles are unchanged.
EOF
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

node_version_is_supported() {
  local major minor
  IFS=. read -r major minor _ < <(node --version | sed 's/^v//')
  ((major == 20 && minor >= 19)) || ((major >= 22 && (major > 22 || minor >= 12)))
}

install_node_dependencies() {
  local directory="$1"
  local lockfile="$directory/package-lock.json"
  local installed_lock="$directory/node_modules/.package-lock.json"

  if [[ "${FORCE_INSTALL:-0}" == "1" || ! -f "$installed_lock" || "$lockfile" -nt "$installed_lock" ]]; then
    printf 'Installing Node dependencies in %s...\n' "$directory"
    npm ci --prefix "$directory"
  fi
}

is_managed_process() {
  local pid="$1"
  local process_cwd process_command

  process_cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  process_command="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$process_cwd" == "$MIROFISH_DIR" && "$process_command" == *"npm run dev"* ]]
}

stop_process_group() {
  local pid="$1"

  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || return 0
  for _ in {1..50}; do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.1
  done
  kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
}

remove_owned_pid_file() {
  local expected_pid="$1"
  local recorded_pid=""

  [[ -f "$PID_FILE" ]] || return 0
  read -r recorded_pid < "$PID_FILE" || true
  if [[ "$recorded_pid" == "$expected_pid" ]]; then
    rm -f "$PID_FILE"
  fi
}

stop_existing() {
  local pid=""

  [[ -f "$PID_FILE" ]] || return 0
  read -r pid < "$PID_FILE" || true
  if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
    rm -f "$PID_FILE"
    return 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$PID_FILE"
    return 0
  fi
  if ! is_managed_process "$pid"; then
    fail "PID file points to a process not owned by this project: $pid"
  fi

  printf 'Stopping existing MiroFish services (PID %s)...\n' "$pid"
  stop_process_group "$pid"
  remove_owned_pid_file "$pid"
}

cleanup() {
  local status="$?"
  trap - EXIT INT TERM
  if [[ -n "$CHILD_PID" ]]; then
    stop_process_group "$CHILD_PID"
    remove_owned_pid_file "$CHILD_PID"
  fi
  exit "$status"
}

while (($#)); do
  case "$1" in
    --setup-only)
      SETUP_ONLY=true
      ;;
    --skip-install)
      SKIP_INSTALL=true
      ;;
    --stop)
      STOP_ONLY=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      fail "Unknown option: $1"
      ;;
  esac
  shift
done

[[ -d "$MIROFISH_DIR" ]] || fail "MiroFish directory not found: $MIROFISH_DIR"
if [[ "$STOP_ONLY" == true ]]; then
  stop_existing
  printf 'MiroFish is stopped.\n'
  exit 0
fi
require_command node
require_command npm
require_command uv
require_command setsid
node_version_is_supported || fail "Node.js 20.19+ or 22.12+ is required; found $(node --version)"

if [[ -z "${MIROFISH_ENV_FILE:-}" ]]; then
  if [[ -f "$ROOT_DIR/.env" ]]; then
    MIROFISH_ENV_FILE="$ROOT_DIR/.env"
  elif [[ -f "$MIROFISH_DIR/.env" ]]; then
    MIROFISH_ENV_FILE="$MIROFISH_DIR/.env"
  fi
fi

if [[ -n "${MIROFISH_ENV_FILE:-}" ]]; then
  export MIROFISH_ENV_FILE
  printf 'Using environment file: %s\n' "$MIROFISH_ENV_FILE"
elif [[ -z "${LLM_API_KEY:-}" || -z "${ZEP_API_KEY:-}" ]]; then
  cp "$MIROFISH_DIR/.env.example" "$ROOT_DIR/.env"
  printf 'Created %s/.env from the MiroFish template.\n' "$ROOT_DIR"
  if [[ "$SETUP_ONLY" == false ]]; then
    fail "Set LLM_API_KEY and ZEP_API_KEY in $ROOT_DIR/.env, then run this script again"
  fi
fi

if [[ "$SETUP_ONLY" == false ]]; then
  stop_existing
fi

if [[ "$SKIP_INSTALL" == false ]]; then
  install_node_dependencies "$MIROFISH_DIR"
  install_node_dependencies "$MIROFISH_DIR/frontend"
  printf 'Syncing Python dependencies...\n'
  uv sync --project "$MIROFISH_DIR/backend" --frozen
fi

if [[ "$SETUP_ONLY" == true ]]; then
  printf 'Setup complete.\n'
  exit 0
fi

printf 'Starting MiroFish...\n'
printf 'Frontend: http://localhost:3000\n'
printf 'Backend:  http://localhost:5001/health\n'
printf 'Hot reload is enabled for frontend and backend source changes.\n'
export FLASK_USE_RELOADER=true
cd "$MIROFISH_DIR"
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
setsid npm run dev &
CHILD_PID=$!
printf '%s\n' "$CHILD_PID" > "$PID_FILE"
wait "$CHILD_PID"
