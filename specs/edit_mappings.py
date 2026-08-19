#!/usr/bin/env python3
"""Hand-edit mappings.toml on top of `shotgun init`'s auto-diff output.

Everything here is a deliberate, verified correction -- see PROMPT.md's
"Research the Actual APIs" section and the Anvil README for the reasoning.
Run after every `shotgun init`/`shotgun sync` re-generation.
"""
import tomlkit

PATH = "mappings.toml"

doc = tomlkit.parse(open(PATH).read())

# ---------------------------------------------------------------------
# Settings: pagination + synthesized rate-limit headers
# ---------------------------------------------------------------------
settings = doc["settings"]
# The `gh` CLI (and other GitHub Enterprise Server-aware clients) request
# /api/v3/... for any host that isn't literally github.com/api.github.com,
# even though our mapping's endpoints are written against the plain
# github.com path shape.
settings["source_base_path"] = "/api/v3"
pagination = settings.setdefault("pagination", tomlkit.table())
pagination["rewrite_link_urls"] = True
param_map = pagination.setdefault("param_map", tomlkit.table())
param_map["per_page"] = "limit"

synth = tomlkit.table()
# Forgejo has no rate limiting by default, so these are honest placeholders,
# not real countdowns -- generous enough that no client backs off, present
# so tools that merely check for the header's existence don't choke.
synth["X-RateLimit-Limit"] = "5000"
synth["X-RateLimit-Remaining"] = "4999"
synth["X-RateLimit-Used"] = "1"
synth["X-RateLimit-Resource"] = "core"
synth["X-RateLimit-Reset"] = "4102444800"  # 2100-01-01T00:00:00Z, static
settings["synthesized_response_headers"] = synth

endpoints = doc["endpoints"]
schemas = doc["schemas"]


def find_endpoint(source):
    for e in endpoints:
        if e["source"] == source:
            return e
    raise KeyError(source)


def find_schema(name):
    for s in schemas:
        if s["name"] == name:
            return s
    raise KeyError(name)


# ---------------------------------------------------------------------
# Generic fix: GitHub `homepage` (repo) / `blog` (user) both correspond to
# Forgejo's `website` -- auto-diff can't guess renames, so every
# repository- and user-shaped block independently lists `homepage`/`blog`
# as a GitHub-only default and `website` as a Forgejo-only drop. Collapse
# that into one rename wherever it appears.
# ---------------------------------------------------------------------
def apply_homepage_website_rename(block, source_field):
    resp = block.get("response", block)
    drops = resp.get("drops")
    defaults = resp.get("defaults")
    if drops is None or defaults is None:
        return False
    if "website" not in drops or source_field not in defaults:
        return False
    drops.remove("website")
    del defaults[source_field]
    renames = resp.setdefault("renames", tomlkit.table())
    renames[source_field] = "website"
    return True


touched_repo = []
for e in endpoints:
    if apply_homepage_website_rename(e, "homepage"):
        e["edited"] = True
        touched_repo.append(e["source"])
for s in schemas:
    if apply_homepage_website_rename(s, "homepage"):
        s["edited"] = True
        touched_repo.append(f"schema:{s['name']}")
print("homepage->website rename applied to:", touched_repo)

# ---------------------------------------------------------------------
# GET /user, GET /users/{username}, GET /repos/{owner}/{repo}/contents/{path}
#
# GitHub's response schema for these three is a `oneOf` discriminated
# union (private-user/public-user, content-file/-directory/-symlink/
# -submodule). Shotgun's diff engine doesn't resolve `oneOf`, so it saw
# ZERO source fields and listed the *entire* matching Forgejo object as
# "drops" -- which would silently strip every field from the response.
# Verified by hand against GitHub's actual User/Content object shapes.
# ---------------------------------------------------------------------
USER_SAME_NAME = [
    "id", "login", "avatar_url", "html_url", "email",
]
USER_RENAMES = {
    "name": "full_name",
    "created_at": "created",
    "blog": "website",
    "bio": "description",
}
USER_FORGEJO_ONLY_DROPS = [
    "active", "is_admin", "last_login", "language", "location",
    "login_name", "prohibit_login", "pronouns", "restricted",
    "source_id", "starred_repos_count", "visibility",
]
USER_GITHUB_ONLY_DEFAULTS = {
    "node_id": "",
    "type": "User",
    "site_admin": False,
    "company": "",
    "hireable": False,
    "public_repos": 0,
    "public_gists": 0,
    "followers": 0,
    "following": 0,
    "updated_at": "",
    "twitter_username": "",
}
USER_NOTE = (
    "GitHub's response schema here is a `oneOf` discriminated union "
    "(private-user/public-user), which Shotgun's diff engine doesn't "
    "resolve -- auto-diff saw 0 source fields and listed the entire "
    "Forgejo User object as drops. Hand-corrected against GitHub's real "
    "User object: same-name fields pass through, name/created_at/blog/bio "
    "are renamed, Forgejo-only account-admin fields are genuinely dropped, "
    "and GitHub-only fields Forgejo has no concept of (plan, "
    "two_factor_authentication, company, hireable, etc.) are defaulted."
)

for source in ("GET /user", "GET /users/{username}"):
    e = find_endpoint(source)
    resp = e.setdefault("response", tomlkit.table())
    drops = tomlkit.array()
    drops.extend(USER_FORGEJO_ONLY_DROPS)
    resp["drops"] = drops.multiline(True)
    renames = tomlkit.table()
    for k, v in USER_RENAMES.items():
        renames[k] = v
    resp["renames"] = renames
    defaults = tomlkit.table()
    for k, v in USER_GITHUB_ONLY_DEFAULTS.items():
        defaults[k] = v
    resp["defaults"] = defaults
    e["edited"] = True
    e["note"] = USER_NOTE

# Content: same-name fields (content, download_url, encoding, git_url,
# html_url, name, path, sha, size, type, url, _links) already match on
# both sides once we stop treating the whole target as one-sided drops.
CONTENT_FORGEJO_ONLY_DROPS = [
    "last_commit_sha", "last_commit_when", "submodule_git_url", "target",
]
CONTENT_NOTE = (
    "GitHub's response schema is a `oneOf` over content-file/-directory/"
    "-symlink/-submodule, which Shotgun's diff engine doesn't resolve -- "
    "auto-diff saw 0 source fields and listed the entire Forgejo "
    "ContentsResponse as drops. Hand-corrected: Forgejo's ContentsResponse "
    "already uses the same field names as GitHub's content-file shape "
    "(content, sha, size, encoding, download_url, html_url, git_url, "
    "_links, ...), so only Forgejo-only fields are actually dropped."
)
e = find_endpoint("GET /repos/{owner}/{repo}/contents/{path}")
resp = e.setdefault("response", tomlkit.table())
drops = tomlkit.array()
drops.extend(CONTENT_FORGEJO_ONLY_DROPS)
resp["drops"] = drops.multiline(True)
if "defaults" in resp:
    del resp["defaults"]
if "renames" in resp:
    del resp["renames"]
e["edited"] = True
e["note"] = CONTENT_NOTE

# ---------------------------------------------------------------------
# PR merge: GitHub uses PUT, Forgejo uses POST, on the same normalized
# path shape (`{pull_number}` vs `{index}`). Left unmapped by auto-diff
# (method mismatch is never assumed correct) -- confirmed and filled in.
# ---------------------------------------------------------------------
e = find_endpoint("PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge")
e["target"] = "POST /repos/{owner}/{repo}/pulls/{index}/merge"
path_params = e.setdefault("path_params", tomlkit.table())
path_params["pull_number"] = "index"
e["edited"] = True
e["note"] = (
    "Forgejo merges via POST, not PUT, on the equivalent path "
    "(/pulls/{index}/merge vs /pulls/{pull_number}/merge). Confirmed by "
    "hand; auto-diff leaves method mismatches unmapped rather than "
    "guessing."
)

# ---------------------------------------------------------------------
# Search: different paths entirely (no path/operationId match), but real
# functional equivalents exist.
# ---------------------------------------------------------------------
e = find_endpoint("GET /search/repositories")
e["target"] = "GET /repos/search"
e["edited"] = True
e["note"] = (
    "Forgejo's repo search lives at /repos/search, not /search/repositories "
    "-- no path/operationId match, mapped by hand. Query syntax differs: "
    "GitHub's `q` supports qualifiers like `language:` / `stars:>N` inline "
    "in the string; Forgejo takes separate `q`, `topic`, `language` etc. "
    "params. Simple keyword searches work; GitHub qualifier syntax does not "
    "translate and is passed through as a literal (mostly useless) string."
)

e = find_endpoint("GET /search/issues")
e["target"] = "GET /repos/issues/search"
e["edited"] = True
e["note"] = (
    "Forgejo's issue/PR search lives at /repos/issues/search -- no path "
    "match, mapped by hand. Same query-syntax caveat as repo search: "
    "GitHub's qualifier-in-string `q` syntax (`repo:x label:y`) doesn't "
    "translate to Forgejo's separate query params."
)

# Forgejo wraps repo search results in {"data": [...], "ok": true};
# GitHub wraps them in {"items": [...], "total_count": N,
# "incomplete_results": false}. Same shape (wrapped array), different key.
e = find_endpoint("GET /search/repositories")
resp = e.setdefault("response", tomlkit.table())
renames = resp.setdefault("renames", tomlkit.table())
renames["items"] = "data"
drops = resp.setdefault("drops", tomlkit.array())
if "ok" not in drops:
    drops.append("ok")
defaults = resp.setdefault("defaults", tomlkit.table())
defaults["total_count"] = 0
defaults["incomplete_results"] = False
e["note"] = (
    e.get("note", "")
    + " Forgejo wraps results as {data, ok}; GitHub wraps as {items, "
    "total_count, incomplete_results} -- `items` is aliased to `data`, but "
    "`total_count`/`incomplete_results` are Forgejo's X-Total-Count header, "
    "not body fields, so they're defaulted rather than accurately populated."
)

with open(PATH, "w") as f:
    f.write(tomlkit.dumps(doc))

print("done")
