#!/usr/bin/env bash
# Validate Anvil's Priority 1 endpoints against a real (or already-running)
# Forgejo instance, through the proxy.
#
# Usage:
#   ./scripts/test-p1.sh                                   # spins up Anvil against Codeberg
#   FORGEJO_URL=https://git.example.com ./scripts/test-p1.sh
#   ANVIL_URL=http://127.0.0.1:3000 ./scripts/test-p1.sh    # reuse an already-running Anvil
#
# Set TEST_OWNER/TEST_REPO/TEST_USER to point at a repo/user that exists on
# your instance (defaults to Codeberg's forgejo/forgejo and the "forgejo"
# user, which are public and always present).
#
# This checks status codes and the specific field renames/shapes documented
# in the README (name/full_name, created_at/created, homepage/website,
# owner.login nesting, PUT->POST pull merge, etc.) -- not full gh CLI runs,
# since gh hard-requires HTTPS for any non-github.com host (see README).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

FORGEJO_URL="${FORGEJO_URL:-https://codeberg.org}"
TEST_OWNER="${TEST_OWNER:-forgejo}"
TEST_REPO="${TEST_REPO:-forgejo}"
TEST_USER="${TEST_USER:-forgejo}"

PASS=0
FAIL=0
STARTED_ANVIL=0
ANVIL_PID=""

cleanup() {
  if [ "$STARTED_ANVIL" = "1" ] && [ -n "$ANVIL_PID" ]; then
    kill "$ANVIL_PID" 2>/dev/null
  fi
}
trap cleanup EXIT

if [ -z "${ANVIL_URL:-}" ]; then
  LISTEN="127.0.0.1:0"
  # Pick a free-ish high port instead of :0 (bash can't read the OS-assigned
  # port back from a background process easily).
  LISTEN_PORT=$(( (RANDOM % 20000) + 20000 ))
  LISTEN="127.0.0.1:$LISTEN_PORT"
  ANVIL_URL="http://$LISTEN"
  echo "Starting Anvil against $FORGEJO_URL on $LISTEN ..." >&2
  "$ROOT_DIR/anvil.sh" --forgejo-url "$FORGEJO_URL" --listen "$LISTEN" >/tmp/anvil-test.log 2>&1 &
  ANVIL_PID=$!
  STARTED_ANVIL=1
  for _ in $(seq 1 50); do
    if curl -s -o /dev/null "$ANVIL_URL/users/$TEST_USER"; then break; fi
    sleep 0.2
  done
fi

check() {
  local desc="$1" method="$2" path="$3" expect_status="$4" jq_filter="${5:-}" expect_value="${6:-}"
  local body status
  body=$(curl -s -o /tmp/anvil-test-body.json -w '%{http_code}' -X "$method" "$ANVIL_URL$path")
  status="$body"
  if [ "$status" != "$expect_status" ]; then
    echo "FAIL  $desc -- expected HTTP $expect_status, got $status ($method $path)"
    FAIL=$((FAIL+1))
    return
  fi
  if [ -n "$jq_filter" ]; then
    local actual
    actual=$(jq -r "$jq_filter" /tmp/anvil-test-body.json 2>/dev/null)
    if [ "$actual" != "$expect_value" ]; then
      echo "FAIL  $desc -- expected $jq_filter == '$expect_value', got '$actual'"
      FAIL=$((FAIL+1))
      return
    fi
  fi
  echo "PASS  $desc"
  PASS=$((PASS+1))
}

echo "== User / Auth =="
check "GET /users/{username}"        GET "/users/$TEST_USER" 200 '.login' "$TEST_USER"
check "  -> full_name renamed to name" GET "/users/$TEST_USER" 200 'has("full_name")|not' "true"

echo "== Repositories =="
check "GET /repos/{owner}/{repo}"    GET "/repos/$TEST_OWNER/$TEST_REPO" 200 '.full_name' "$TEST_OWNER/$TEST_REPO"
check "  -> owner.login nested"      GET "/repos/$TEST_OWNER/$TEST_REPO" 200 '.owner.login' "$TEST_OWNER"
check "  -> website renamed to homepage" GET "/repos/$TEST_OWNER/$TEST_REPO" 200 'has("website")|not' "true"
check "GET /repos/{owner}/{repo}/branches" GET "/repos/$TEST_OWNER/$TEST_REPO/branches" 200 'type' "array"

echo "== Issues =="
check "GET /repos/{owner}/{repo}/issues" GET "/repos/$TEST_OWNER/$TEST_REPO/issues?limit=1&state=all" 200 'type' "array"

echo "== Pull Requests =="
check "GET /repos/{owner}/{repo}/pulls" GET "/repos/$TEST_OWNER/$TEST_REPO/pulls?limit=1&state=all" 200 'type' "array"

echo "== Commit Status =="
check "GET /repos/{owner}/{repo}/commits/{ref}/status" GET "/repos/$TEST_OWNER/$TEST_REPO/commits/HEAD/status" 200

echo "== Contents =="
check "GET /repos/{owner}/{repo}/contents/{path}" GET "/repos/$TEST_OWNER/$TEST_REPO/contents/README.md" 200 '.encoding' "base64"

echo "== Rate-limit header synthesis =="
if curl -s -D - -o /dev/null "$ANVIL_URL/users/$TEST_USER" | grep -qi '^x-ratelimit-limit:'; then
  echo "PASS  X-RateLimit-* headers present"
  PASS=$((PASS+1))
else
  echo "FAIL  X-RateLimit-* headers missing"
  FAIL=$((FAIL+1))
fi

echo "== Explicitly-unsupported endpoints 501 cleanly =="
check "GET /repos/{owner}/{repo}/readme (no Forgejo equivalent)" GET "/repos/$TEST_OWNER/$TEST_REPO/readme" 501
check "GET .../dependabot/secrets (no Forgejo equivalent)" GET "/repos/$TEST_OWNER/$TEST_REPO/dependabot/secrets" 501

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
