<p align="center">
  <img src="assets/banner.png" alt="Anvil — GitHub-shaped tools, hammering on your own forge" width="100%">
</p>

<h1 align="center">Anvil</h1>

<p align="center">
  <strong>Point GitHub-shaped tools at your Forgejo instance. No rewrites.</strong><br>
  <code>gh</code> · Renovate · CI scripts → your own forge, translated at the anvil.
</p>

---

Anvil is a proxy that lets GitHub-compatible tools talk to a [Forgejo](https://forgejo.org) instance as if it were GitHub. `gh repo list` works. Renovate works. CI status reporting works. The tools never learn the difference.

Under the hood it's [Shotgun](https://github.com/ThatXliner/shotgun) — an OpenAPI-to-OpenAPI translation proxy — wearing a curated GitHub↔Forgejo configuration: a hand-checked `mappings.toml`, tested live against [Codeberg](https://codeberg.org). The value is the mapping file, the one-command experience, and the testing.

## Quickstart

```sh
git clone https://github.com/ThatXliner/shotgun shotgun
git clone https://github.com/ThatXliner/anvil anvil && cd anvil
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

**86% of endpoints (75/87) are mapped**, verified live against Codeberg.

**Working:** users (including profile edits via `PATCH /user`), repos, branches, issues, PRs (including merge — GitHub's `PUT` becomes Forgejo's `POST`), commit statuses, contents, **the repo readme** (Forgejo has no readme endpoint — Anvil serves it from the contents API; it matches a readme literally named `README.md`), labels, milestones, releases, webhooks, collaborators, git refs (read), pagination (`per_page` → `limit`, `Link` headers rewritten), Actions (runs/artifacts/secrets), search (keyword only).

**Not supported:** git ref create/update (Forgejo's API only reads refs), Actions variable creation (Forgejo puts the name in the path), reading a single secret back, Dependabot, Codespaces, GitHub Apps, GraphQL, Packages, code scanning. These return **501** — the same answer GitHub would give, so your tooling fails fast and loudly instead of silently misbehaving.

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
4. Test against a real instance with `curl`, or add a case to the live endpoint test suite (`scripts/test-p1.sh`).

## Project structure

```
mappings.toml            — the mapping configuration (start here)
anvil.sh                 — entrypoint script
specs/                   — trimmed and full OpenAPI specs, plus trim/edit scripts
scripts/test-p1.sh       — live endpoint tests
scripts/dev-tls-proxy.py — local HTTPS proxy for gh testing
Dockerfile               — containerized alternative (build from parent dir containing both anvil/ and shotgun/)
```

---

<p align="center">
  <a href="https://thatxliner.github.io/anvil/">Landing page</a> ·
  Built on <a href="https://github.com/ThatXliner/shotgun">Shotgun</a> ·
  Sibling project — same night sky, warmer fire.
</p>
