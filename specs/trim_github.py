#!/usr/bin/env python3
"""Extract a subset of paths (+ transitively-referenced components.schemas)
from the full GitHub OpenAPI spec into a small, focused spec for Anvil."""
import json
import re
import sys

SRC = "specs/full/github-api.json"
OUT = "specs/github-rest-api.json"

# method, path pairs we want in the trimmed spec.
PATHS = [
    # User / Auth
    "/user",
    "/users/{username}",
    # Repositories
    "/repos/{owner}/{repo}",
    "/user/repos",
    "/users/{username}/repos",
    "/orgs/{org}/repos",
    "/repos/{owner}/{repo}/branches",
    "/repos/{owner}/{repo}/branches/{branch}",
    # Issues
    "/repos/{owner}/{repo}/issues",
    "/repos/{owner}/{repo}/issues/{issue_number}",
    "/repos/{owner}/{repo}/issues/{issue_number}/comments",
    # Pull requests
    "/repos/{owner}/{repo}/pulls",
    "/repos/{owner}/{repo}/pulls/{pull_number}",
    "/repos/{owner}/{repo}/pulls/{pull_number}/merge",
    # Commit status
    "/repos/{owner}/{repo}/statuses/{sha}",
    "/repos/{owner}/{repo}/commits/{ref}/status",
    # Contents
    "/repos/{owner}/{repo}/contents/{path}",
    "/repos/{owner}/{repo}/readme",
    # --- Priority 2 ---
    "/repos/{owner}/{repo}/labels",
    "/repos/{owner}/{repo}/labels/{name}",
    "/repos/{owner}/{repo}/issues/{issue_number}/labels",
    "/repos/{owner}/{repo}/milestones",
    "/repos/{owner}/{repo}/milestones/{milestone_number}",
    "/repos/{owner}/{repo}/releases",
    "/repos/{owner}/{repo}/releases/{release_id}",
    "/repos/{owner}/{repo}/releases/latest",
    "/repos/{owner}/{repo}/hooks",
    "/repos/{owner}/{repo}/hooks/{hook_id}",
    "/orgs/{org}/members",
    "/orgs/{org}/members/{username}",
    "/repos/{owner}/{repo}/git/refs/{ref}",
    "/repos/{owner}/{repo}/git/refs",
    "/repos/{owner}/{repo}/tags",
    "/repos/{owner}/{repo}/collaborators",
    "/repos/{owner}/{repo}/collaborators/{username}",
    "/search/repositories",
    "/search/issues",
    # --- explicitly-still-supported categories (best-effort) ---
    "/repos/{owner}/{repo}/actions/runs",
    "/repos/{owner}/{repo}/actions/runs/{run_id}",
    "/repos/{owner}/{repo}/actions/artifacts",
    "/repos/{owner}/{repo}/actions/secrets",
    "/repos/{owner}/{repo}/actions/secrets/{secret_name}",
    "/repos/{owner}/{repo}/actions/variables",
    "/repos/{owner}/{repo}/dependabot/secrets",
    "/repos/{owner}/{repo}/dependabot/secrets/{secret_name}",
    "/user/codespaces",
    "/repos/{owner}/{repo}/codespaces",
]

with open(SRC) as f:
    spec = json.load(f)

full_paths = spec["paths"]
missing = [p for p in PATHS if p not in full_paths]
if missing:
    print("WARNING: paths not found in source spec:", missing, file=sys.stderr)

trimmed_paths = {p: full_paths[p] for p in PATHS if p in full_paths}

ref_re = re.compile(r'"\$ref"\s*:\s*"#/components/schemas/([^"]+)"')

def find_refs(obj):
    return set(ref_re.findall(json.dumps(obj)))

schemas = spec["components"]["schemas"]
needed = set()
frontier = find_refs(trimmed_paths)
while frontier:
    needed |= frontier
    next_frontier = set()
    for name in frontier:
        if name in schemas:
            next_frontier |= find_refs(schemas[name])
    frontier = next_frontier - needed

trimmed_schemas = {name: schemas[name] for name in needed if name in schemas}

out = {
    "openapi": spec.get("openapi", "3.0.3"),
    "info": {
        "title": "GitHub REST API (Anvil trimmed subset)",
        "version": spec.get("info", {}).get("version", "unknown"),
        "description": "Subset of github/rest-api-description covering Anvil's Priority 1/2 endpoints. Regenerate with specs/trim_github.py.",
    },
    "servers": spec.get("servers", []),
    "paths": trimmed_paths,
    "components": {"schemas": trimmed_schemas},
}

with open(OUT, "w") as f:
    json.dump(out, f, indent=2)
    f.write("\n")

print(f"wrote {OUT}: {len(trimmed_paths)} paths, {len(trimmed_schemas)} schemas")
