# Anvil

A proxy that lets GitHub-compatible tools (`gh`, Renovate, CI scripts) talk to a [Forgejo](https://forgejo.org) instance — no rewrites needed.

Built on [Shotgun](https://github.com/ThatXliner/shotgun), an OpenAPI-to-OpenAPI translation proxy. Anvil is the opinionated GitHub↔Forgejo configuration: a curated `mappings.toml` tested against [Codeberg](https://codeberg.org).

## Quickstart

```sh
git clone <shotgun-repo-url> shotgun
git clone <this-repo> anvil && cd anvil
./anvil.sh --forgejo-url https://your-forgejo.example.com
```

First run builds Shotgun from `../shotgun` (needs a [Rust toolchain](https://rustup.rs)). After that it starts instantly.

If you have `shotgun` on `PATH` or elsewhere, set `$SHOTGUN_DIR` — see `anvil.sh --help`.

```sh
# Test it
GH_HOST=127.0.0.1:3000 GH_TOKEN=<forgejo-token> gh api user
```

> **Note:** `gh` requires HTTPS. Anvil speaks plain HTTP — put a reverse proxy (Caddy, nginx, Cloudflare Tunnel) in front for `gh` use. `scripts/dev-tls-proxy.py` provides a self-signed cert for local testing. Tools that don't hardcode HTTPS (curl, CI scripts, Renovate) work directly.

## Coverage

82% of endpoints (72/87) are mapped. Verified live against Codeberg via `scripts/test-p1.sh`.

**Working:** users, repos, branches, issues, PRs (including merge), commit statuses, contents, labels, milestones, releases, webhooks, collaborators, git refs (read), pagination, Actions (runs/artifacts/secrets), search (keyword only).

**Not supported:** `GET /repos/{owner}/{repo}/readme` (no Forgejo equivalent), `PATCH /user`, git ref create/update, Dependabot, Codespaces, GitHub Apps, GraphQL, Packages, code scanning. These return 501.

## Extending

1. Add the endpoint path to `specs/trim_github.py` and/or `specs/trim_forgejo.py`.
2. Regenerate specs and sync mappings:
   ```sh
   python3 specs/trim_github.py
   python3 specs/trim_forgejo.py
   shotgun sync --source specs/github-rest-api.json --target specs/forgejo-api.json --mappings mappings.toml
   python3 specs/edit_mappings.py
   ```
3. Check `shotgun validate --mappings mappings.toml` for unresolved fields — add renames in `mappings.toml` or `specs/edit_mappings.py`.
4. Test against a real instance with `curl` or add a case to `scripts/test-p1.sh`.

## Project structure

```
mappings.toml          — the mapping configuration (start here)
anvil.sh               — entrypoint script
specs/                 — trimmed and full OpenAPI specs, plus trim/edit scripts
scripts/test-p1.sh     — live endpoint tests
scripts/dev-tls-proxy.py — local HTTPS proxy for gh testing
Dockerfile             — containerized alternative (build from parent dir containing both anvil/ and shotgun/)
```
