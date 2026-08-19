# Anvil

**Built on [Shotgun](https://github.com/ThatXliner/shotgun)** — a generic
OpenAPI-to-OpenAPI translation proxy: give it two specs, it diffs them,
auto-maps what lines up, and runs a proxy that translates requests and
responses between the two shapes.

Anvil points GitHub-shaped tooling — `gh`, Renovate, basic CI scripts, deploy
hooks — at a self-hosted [Forgejo](https://forgejo.org) instance without
rewriting any of it. Shotgun doesn't know what a "repository" is; Anvil is
the opinionated GitHub↔Forgejo configuration of it: a curated,
hand-verified `mappings.toml` plus the OpenAPI specs it was built from,
tested against a real, public Forgejo instance (Codeberg). Anvil doesn't
vendor or fork Shotgun — it's a sibling project that runs on a real Shotgun
checkout, and every gap it hit in Shotgun's mapping format (see "Known
Shotgun bugs fixed along the way" below) was fixed upstream in Shotgun
itself, not worked around here.

## Quickstart

```sh
git clone <shotgun-repo-url> shotgun    # sibling checkout; anvil.sh looks for ../shotgun
git clone <this-repo> anvil && cd anvil
./anvil.sh --forgejo-url https://your-forgejo.example.com
GH_HOST=127.0.0.1:3000 GH_TOKEN=<a-forgejo-access-token> gh api user
```

The first run builds Shotgun from `../shotgun` (needs a Rust toolchain — see
[rustup.rs](https://rustup.rs)); after that it starts instantly. If you
already have a `shotgun` binary on `PATH`, or a checkout somewhere else, set
`$SHOTGUN_DIR` or just make sure `shotgun` resolves on `PATH` — see
`anvil.sh --help` / its resolution order at the top of the script.
`FORGEJO_URL` env var works instead of `--forgejo-url`.

**Read the `gh` CLI + HTTPS section below before you reach for `gh` specifically** —
curl and most other GitHub-API clients work against plain HTTP right away.

## What works

Verified live against `https://codeberg.org` (a public Forgejo instance) via
`scripts/test-p1.sh`.

| Endpoint | Status | Notes |
|---|---|---|
| `GET /user`, `GET /users/{username}` | ✅ | `name`↔`full_name`, `created_at`↔`created`, `blog`↔`website`, `bio`↔`description` renamed by hand (GitHub's response schema is a `oneOf` union Shotgun's auto-diff can't resolve — see below) |
| `GET /repos/{owner}/{repo}` | ✅ | `homepage`↔`website` renamed; `owner`/`parent` nested and recursively mapped |
| `GET /user/repos`, `GET /users/{username}/repos`, `GET /orgs/{org}/repos`, `POST /user/repos` | ✅ | same repository renames |
| `GET /repos/{owner}/{repo}/branches` | ✅ | |
| Issues: list/get/create/update, comments list/create | ✅ | `issue_number`↔`index` path param |
| Pull requests: list/get/create/update | ✅ | `pull_number`↔`index` path param |
| **PR merge** (`PUT .../merge`) | ✅ | Forgejo merges via `POST`, not `PUT` — auto-diff leaves method mismatches unmapped by design; hand-confirmed and mapped |
| Commit status: `POST /statuses/{sha}`, `GET /commits/{ref}/status` | ✅ | |
| `GET /repos/{owner}/{repo}/contents/{path}` | ✅ | GitHub's response is also a `oneOf` union (file/dir/symlink/submodule) — hand-corrected the same way as `/user` |
| Labels, milestones, releases, webhooks (P2) | ✅ | auto-mapped cleanly, field names already align |
| Git refs (P2, read) | ✅ | list/get only |
| Collaborators (P2) | ✅ | |
| `GET /search/repositories` → `/repos/search` | ⚠️ | different path, mapped by hand; GitHub's `q:qualifier` string syntax doesn't translate to Forgejo's separate query params — plain keyword search works |
| `GET /search/issues` → `/repos/issues/search` | ⚠️ | same query-syntax caveat |
| Pagination (`per_page`↔`limit`, `Link` header rewriting) | ✅ | |
| Rate-limit headers (`X-RateLimit-*`) | ⚠️ | synthesized static values (Forgejo doesn't rate-limit by default) — presence/shape is GitHub-correct, the numbers aren't real |
| Actions: list/get workflow runs, artifacts, secrets (list) | ✅ | Forgejo's Actions API covers a meaningful subset |

## What doesn't

- **`gh` CLI requires HTTPS.** `gh` (like other GitHub Enterprise
  Server-aware clients) treats any host that isn't literally `github.com` as
  a GHES instance: it always requests `https://` and prefixes every path
  with `/api/v3` (Anvil handles the `/api/v3` prefix via
  `settings.source_base_path` in `mappings.toml`; that part's solved). Anvil
  itself only speaks plain HTTP — TLS termination is a deployment concern,
  not something baked into the proxy. Put a real reverse proxy in front
  (Caddy with auto-HTTPS, nginx, a Cloudflare Tunnel) for real use.
  `scripts/dev-tls-proxy.py` self-signs a cert for **local testing only** —
  it does not add anything to your system trust store; you decide whether
  and how to trust it (`curl --cacert`, or your own OS-specific step). Tools
  that don't hardcode HTTPS (curl, most CI scripts, Renovate custom
  endpoints) work against Anvil's plain HTTP listener today.
- **`GET /repos/{owner}/{repo}/readme`** has no Forgejo equivalent path at
  all — 501s. Fetch `contents/README.md` directly instead.
- **`PATCH /user`** (update the authenticated user) — Forgejo's API has no
  matching "update self" endpoint — 501s.
- **Git ref creation/update** (`POST`/`PATCH .../git/refs`) — Forgejo's
  `/git/refs` is read-only in its own API; refs are created through other
  endpoints (branches, tags) with different shapes that don't line up
  1:1 — left unmapped rather than faked.
- **Dependabot and Codespaces** — Forgejo has no equivalent concept at all
  (verified: zero matching paths in its OpenAPI spec). These 501 with a
  clear message rather than silently doing nothing.
- **GitHub Apps, GraphQL (`/graphql`), Packages, code scanning/security
  advisories** — out of scope by design, 501.
- **`type_conflicts` fields** (`state` on issues/PRs/commit statuses,
  `workflow_id`, a few others) — Shotgun's spec parser sometimes reports a
  same-name field as type-mismatched when the underlying value is actually
  compatible at runtime (e.g. Forgejo's OpenAPI spec models `state` via a
  `$ref`'d enum type, which the parser classifies as "object" even though
  real responses send a plain string). Verified against live Codeberg
  responses that these pass through correctly unchanged — Shotgun never
  silently coerces a flagged field, so nothing is lost, but `shotgun
  validate` will keep listing them until Shotgun's parser resolves `$ref`s
  to their underlying primitive type.
- **`Link` header rewriting uses a placeholder host** (`proxy.local`)
  instead of the actual address the client connected through — pagination
  URLs are structurally correct (right path, right query params) but not
  literally dereferenceable as printed. A Shotgun limitation, not Anvil-specific.
- Coverage is 72/87 endpoints in the trimmed spec (82%) — the gaps above
  account for all 15. Run `../shotgun/target/release/shotgun validate
  --mappings mappings.toml` for the live list.

## How it's built

```
anvil/
  mappings.toml           the actual product -- read this first
  specs/
    github-rest-api.json  trimmed GitHub OpenAPI subset (P1 + P2 + Actions/Dependabot/Codespaces paths)
    forgejo-api.json      trimmed Forgejo swagger subset (from Codeberg's /swagger.v1.json)
    full/                 untrimmed source specs, kept for regenerating the subsets
    trim_github.py        regenerate specs/github-rest-api.json from specs/full/github-api.json
    trim_forgejo.py       regenerate specs/forgejo-api.json from specs/full/forgejo-api.json
    edit_mappings.py      every hand-edit on top of `shotgun init`'s auto-diff, scripted and idempotent
  anvil.sh                 the one-command entrypoint -- builds/uses ../shotgun (or $SHOTGUN_DIR, or `shotgun` on PATH)
  Dockerfile                containerized alternative; build from the parent dir containing both anvil/ and shotgun/ (untested in this environment -- no Docker daemon here)
  scripts/
    test-p1.sh             validates the Priority 1 endpoints against a live Forgejo instance
    dev-tls-proxy.py       local-only HTTPS front door for testing `gh` (see "What doesn't" above)
```

**Regenerating the mapping file** after a spec update:

```sh
python3 specs/trim_github.py      # refresh specs/github-rest-api.json from specs/full/github-api.json
python3 specs/trim_forgejo.py     # refresh specs/forgejo-api.json from specs/full/forgejo-api.json
../shotgun/target/release/shotgun sync \
  --source specs/github-rest-api.json --target specs/forgejo-api.json --mappings mappings.toml
python3 specs/edit_mappings.py    # reapply the hand-verified corrections
```

`shotgun sync` preserves every entry marked `edited = true` (everything
`edit_mappings.py` touches) and only re-diffs what auto-diff still owns.
`edit_mappings.py` is written to be safe to re-run — it checks before it
edits, so running it twice on an already-corrected file is a no-op.

## How to extend

1. Add the endpoint's path to `specs/trim_github.py` / `specs/trim_forgejo.py`'s
   `PATHS` list (find the exact path string in `specs/full/*.json`).
2. Re-run the regeneration steps above.
3. Check `../shotgun/target/release/shotgun validate --mappings
   mappings.toml` for what auto-diff couldn't resolve on its own —
   `defaults`/`drops` pairs with the same underlying meaning (GitHub's
   `X` next to Forgejo's `Y`) are the todo list for a rename; add it under
   `[endpoints.response.renames]` (or in `edit_mappings.py` if it's a
   pattern that recurs across many endpoints, e.g. a shared schema field).
4. Test it against a real instance with `curl`, add a case to
   `scripts/test-p1.sh` if it's a Priority 1 endpoint.
5. If Shotgun's mapping format can't express what you need (a header
   Forgejo never sends, a method that differs, a body reshape) — that's a
   Shotgun feature gap, not an Anvil workaround. This project already added
   two: `settings.source_base_path` (strip a client-injected path prefix
   like `gh`'s `/api/v3`) and `settings.synthesized_response_headers`
   (stamp static headers the target never sends), both in `../shotgun`.

## Known Shotgun bugs fixed along the way

Building Anvil against Shotgun's real diff engine (not the toy example
fixture) surfaced a few genuine Shotgun bugs, all fixed and committed
upstream in `../shotgun` (nothing patched or forked here):

- TOML has no `null` — `shotgun init` crashed writing any mapping file with
  an unresolved-type field default. Fixed in `spec/model.rs`.
- Forgejo's Swagger 2.0 spec resolves most response schemas through a
  `#/responses/Name` indirection Shotgun's parser didn't follow, so it saw
  zero fields for nearly every Forgejo endpoint. Fixed in `spec/parser.rs`.
- The proxy forwarded upstream's `Transfer-Encoding`/`Content-Encoding`
  headers verbatim alongside a body it had already fully materialized and
  re-framed, corrupting any chunked response (silently dropped the
  connection with no error — this broke every list endpoint with more than
  a couple of items). Fixed in `proxy/handler.rs`.
