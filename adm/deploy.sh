#!/usr/bin/env bash
#
# Deploy ADM: pull, rebuild the frontend, restart the backend, check it came up.
#
# ADM is two things in one repository and it is easy to update only half of it.
# `git pull` brings the frontend *sources*; the running UI is the built output
# in backend/static, which is gitignored. On 2026-08-06 a deploy pulled a new
# feature, restarted the backend, and served a three-day-old bundle — the new
# button existed in the source and could not be clicked. Hence one command that
# always does both.
#
# Usage (as root, since .git and the service are root-owned):
#   sudo /opt/erg/proxima-node/adm/deploy.sh
#   sudo make -C /opt/erg/proxima-node/adm deploy
#
#   --no-pull    deploy what is already checked out
#   --no-build   backend only, leave the current UI in place

set -euo pipefail

ADM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$ADM_DIR/.." && pwd)"
SERVICE="proxima-adm"
STATIC="$ADM_DIR/backend/static"
STAGING="$ADM_DIR/backend/static.new"

DO_PULL=1
DO_BUILD=1
for arg in "$@"; do
  case "$arg" in
    --no-pull)  DO_PULL=0 ;;
    --no-build) DO_BUILD=0 ;;
    -h|--help)  sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root — .git and $SERVICE both belong to root." >&2
  exit 1
fi

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# ── Pull ─────────────────────────────────────────────────────────────────
if [[ "$DO_PULL" -eq 1 ]]; then
  say "Pulling"
  before="$(git -C "$REPO_DIR" rev-parse HEAD)"
  # Never merge. A deploy that opens an editor or leaves a conflict half
  # applied is worse than one that refuses and says why.
  git -C "$REPO_DIR" pull --ff-only
  after="$(git -C "$REPO_DIR" rev-parse HEAD)"
  if [[ "$before" == "$after" ]]; then
    echo "Already at $(git -C "$REPO_DIR" rev-parse --short HEAD)"
  else
    git -C "$REPO_DIR" --no-pager log --oneline "$before..$after"
  fi
fi

# ── Frontend ─────────────────────────────────────────────────────────────
if [[ "$DO_BUILD" -eq 1 ]]; then
  say "Building the frontend"
  cd "$ADM_DIR/frontend"

  # npm ci wipes and reinstalls, so only pay for it when it would change
  # something: no tree at all, or a lockfile newer than the tree.
  if [[ ! -d node_modules ]] || [[ package-lock.json -nt node_modules ]]; then
    echo "Installing dependencies (this is the slow one)"
    npm ci
  else
    echo "Dependencies are current"
  fi

  # Build into a staging directory rather than over the live one. vite.config
  # sets emptyOutDir, so building straight into backend/static deletes the
  # running UI first and a failed build leaves the panel serving nothing.
  rm -rf "$STAGING"
  npx vite build --outDir "$STAGING" --emptyOutDir

  if [[ ! -s "$STAGING/index.html" ]]; then
    echo "Build produced no index.html — keeping the current UI" >&2
    rm -rf "$STAGING"
    exit 1
  fi

  # Swap. Keep exactly one generation back; enough to roll a bad build back
  # by hand, not enough to accumulate.
  rm -rf "$STATIC.prev"
  [[ -d "$STATIC" ]] && mv "$STATIC" "$STATIC.prev"
  mv "$STAGING" "$STATIC"
  echo "UI replaced — previous build kept at $(basename "$STATIC").prev"
fi

# ── Backend ──────────────────────────────────────────────────────────────
say "Restarting $SERVICE"
systemctl restart "$SERVICE"
sleep 4

if ! systemctl is-active --quiet "$SERVICE"; then
  echo "$SERVICE did not come up:" >&2
  journalctl -u "$SERVICE" -n 20 --no-pager >&2
  exit 1
fi

port="$(systemctl show "$SERVICE" -p Environment --value | tr ' ' '\n' \
        | sed -n 's/^ADM_PORT=//p')"
port="${port:-5002}"
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:$port/" || true)"

say "Result"
echo "revision : $(git -C "$REPO_DIR" rev-parse --short HEAD)"
echo "service  : $(systemctl is-active "$SERVICE")"
echo "http     : $code on port $port"
[[ "$code" == "200" ]] || { echo "Panel did not answer with 200" >&2; exit 1; }
