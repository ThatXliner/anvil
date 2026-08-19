#!/usr/bin/env bash
# Anvil: point GitHub-expecting tools at your Forgejo instance.
#
#   ./anvil.sh --forgejo-url https://git.example.com
#   FORGEJO_URL=https://git.example.com ./anvil.sh
#
# Builds (once) and runs Shotgun -- the generic OpenAPI-to-OpenAPI proxy
# this project is "just" a curated configuration of -- against the
# mappings.toml and specs/ shipped in this repo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

FORGEJO_URL="${FORGEJO_URL:-}"
LISTEN="${ANVIL_LISTEN:-127.0.0.1:3000}"
MAPPINGS="${ANVIL_MAPPINGS:-$SCRIPT_DIR/mappings.toml}"
LOG_LEVEL="${ANVIL_LOG_LEVEL:-info}"
LOG_UNMAPPED=0

usage() {
  cat <<EOF
Usage: anvil.sh --forgejo-url URL [options]

  --forgejo-url URL   Base URL of your Forgejo instance (required; or set FORGEJO_URL)
  --listen ADDR       Address to listen on (default: 127.0.0.1:3000, or \$ANVIL_LISTEN)
  --mappings PATH     Mapping file to use (default: ./mappings.toml)
  --log-level LEVEL   trace|debug|info|warn|error (default: info)
  --log-unmapped      Log requests to endpoints with no mapping
  -h, --help          Show this help

Then point GitHub-API-speaking tools at the proxy, e.g.:
  GH_HOST=127.0.0.1:3000 GH_TOKEN=<forgejo-token> gh repo list
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --forgejo-url) FORGEJO_URL="$2"; shift 2 ;;
    --forgejo-url=*) FORGEJO_URL="${1#*=}"; shift ;;
    --listen) LISTEN="$2"; shift 2 ;;
    --listen=*) LISTEN="${1#*=}"; shift ;;
    --mappings) MAPPINGS="$2"; shift 2 ;;
    --mappings=*) MAPPINGS="${1#*=}"; shift ;;
    --log-level) LOG_LEVEL="$2"; shift 2 ;;
    --log-level=*) LOG_LEVEL="${1#*=}"; shift ;;
    --log-unmapped) LOG_UNMAPPED=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "anvil: unknown argument '$1'" >&2; usage >&2; exit 1 ;;
  esac
done

if [ -z "$FORGEJO_URL" ]; then
  echo "anvil: --forgejo-url (or \$FORGEJO_URL) is required" >&2
  usage >&2
  exit 1
fi

# Anvil isn't a fork of Shotgun and doesn't vendor a copy of it -- it's a
# configuration (mappings.toml + specs) that runs on top of a real Shotgun
# checkout. Resolution order:
#   1. a `shotgun` binary already on PATH
#   2. $SHOTGUN_DIR, if set
#   3. a sibling checkout at ../shotgun (this repo's dev layout)
SHOTGUN_BIN=""
if command -v shotgun >/dev/null 2>&1; then
  SHOTGUN_BIN="$(command -v shotgun)"
else
  SHOTGUN_DIR="${SHOTGUN_DIR:-$SCRIPT_DIR/../shotgun}"
  if [ ! -d "$SHOTGUN_DIR" ]; then
    echo "anvil: no shotgun binary on PATH and no Shotgun checkout at $SHOTGUN_DIR" >&2
    echo "        clone https://github.com/<org>/shotgun next to this repo, set \$SHOTGUN_DIR," >&2
    echo "        or install a 'shotgun' binary on PATH." >&2
    exit 1
  fi
  SHOTGUN_BIN="$SHOTGUN_DIR/target/release/shotgun"
  if [ ! -x "$SHOTGUN_BIN" ]; then
    if ! command -v cargo >/dev/null 2>&1; then
      echo "anvil: shotgun isn't built yet at $SHOTGUN_DIR and 'cargo' isn't on PATH." >&2
      echo "        install Rust (https://rustup.rs) to build it." >&2
      exit 1
    fi
    echo "anvil: building shotgun from $SHOTGUN_DIR (first run only)..." >&2
    (cd "$SHOTGUN_DIR" && cargo build --release --quiet)
  fi
fi

ARGS=(serve --mappings "$MAPPINGS" --target-url "$FORGEJO_URL" --listen "$LISTEN" --log-level "$LOG_LEVEL")
if [ "$LOG_UNMAPPED" = "1" ]; then
  ARGS+=(--log-unmapped)
fi

echo "anvil: proxying GitHub API shape -> $FORGEJO_URL, listening on http://$LISTEN" >&2
echo "anvil: e.g. GH_HOST=$LISTEN GH_TOKEN=<forgejo-token> gh repo list" >&2
exec "$SHOTGUN_BIN" "${ARGS[@]}"
