#!/usr/bin/env python3
"""Extract a subset of paths (+ referenced definitions) from the full
Forgejo swagger.json into a small, focused spec for Anvil."""
import json
import re
import sys

SRC = "specs/full/forgejo-api.json"
OUT = "specs/forgejo-api.json"

PATHS = [
    "/user",
    "/users/{username}",
    "/repos/{owner}/{repo}",
    "/user/repos",
    "/users/{username}/repos",
    "/orgs/{org}/repos",
    "/repos/{owner}/{repo}/branches",
    "/repos/{owner}/{repo}/branches/{branch}",
    "/repos/{owner}/{repo}/issues",
    "/repos/{owner}/{repo}/issues/{index}",
    "/repos/{owner}/{repo}/issues/{index}/comments",
    "/repos/{owner}/{repo}/pulls",
    "/repos/{owner}/{repo}/pulls/{index}",
    "/repos/{owner}/{repo}/pulls/{index}/merge",
    "/repos/{owner}/{repo}/statuses/{sha}",
    "/repos/{owner}/{repo}/commits/{ref}/status",
    "/repos/{owner}/{repo}/contents/{filepath}",
    # P2
    "/repos/{owner}/{repo}/labels",
    "/repos/{owner}/{repo}/labels/{id}",
    "/repos/{owner}/{repo}/issues/{index}/labels",
    "/repos/{owner}/{repo}/milestones",
    "/repos/{owner}/{repo}/milestones/{id}",
    "/repos/{owner}/{repo}/releases",
    "/repos/{owner}/{repo}/releases/{id}",
    "/repos/{owner}/{repo}/releases/latest",
    "/repos/{owner}/{repo}/hooks",
    "/repos/{owner}/{repo}/hooks/{id}",
    "/orgs/{org}/members",
    "/orgs/{org}/members/{username}",
    "/repos/{owner}/{repo}/git/refs",
    "/repos/{owner}/{repo}/git/refs/{ref}",
    "/repos/{owner}/{repo}/tags",
    "/repos/{owner}/{repo}/collaborators",
    "/repos/{owner}/{repo}/collaborators/{collaborator}",
    "/repos/search",
    "/repos/issues/search",
    # Actions (best-effort; Forgejo has no Dependabot/Codespaces concept at all)
    "/repos/{owner}/{repo}/actions/runs",
    "/repos/{owner}/{repo}/actions/runs/{run_id}",
    "/repos/{owner}/{repo}/actions/artifacts",
    "/repos/{owner}/{repo}/actions/secrets",
    "/repos/{owner}/{repo}/actions/secrets/{secretname}",
    "/repos/{owner}/{repo}/actions/variables",
]

with open(SRC) as f:
    spec = json.load(f)

full_paths = spec["paths"]
missing = [p for p in PATHS if p not in full_paths]
if missing:
    print("WARNING: paths not found in source spec:", missing, file=sys.stderr)

trimmed_paths = {p: full_paths[p] for p in PATHS if p in full_paths}

def_re = re.compile(r'"\$ref"\s*:\s*"#/definitions/([^"]+)"')
resp_re = re.compile(r'"\$ref"\s*:\s*"#/responses/([^"]+)"')

definitions = spec["definitions"]
responses = spec.get("responses", {})

# Swagger 2.0 responses can $ref into #/responses/Name, which itself wraps a
# #/definitions/Name schema -- both ref namespaces need transitive resolution.
needed_defs = set()
needed_resps = set()
def_frontier = def_re.findall(json.dumps(trimmed_paths))
resp_frontier = resp_re.findall(json.dumps(trimmed_paths))
while def_frontier or resp_frontier:
    new_defs = set(def_frontier) - needed_defs
    new_resps = set(resp_frontier) - needed_resps
    needed_defs |= new_defs
    needed_resps |= new_resps
    def_frontier = []
    resp_frontier = []
    for name in new_defs:
        if name in definitions:
            blob = json.dumps(definitions[name])
            def_frontier += def_re.findall(blob)
            resp_frontier += resp_re.findall(blob)
    for name in new_resps:
        if name in responses:
            blob = json.dumps(responses[name])
            def_frontier += def_re.findall(blob)
            resp_frontier += resp_re.findall(blob)

trimmed_defs = {name: definitions[name] for name in needed_defs if name in definitions}
trimmed_resps = {name: responses[name] for name in needed_resps if name in responses}

out = dict(spec)
out["paths"] = trimmed_paths
out["definitions"] = trimmed_defs
out["responses"] = trimmed_resps
out["info"] = dict(spec.get("info", {}))
out["info"]["description"] = "Subset of Codeberg's /swagger.v1.json covering Anvil's Priority 1/2 endpoints. Regenerate with specs/trim_forgejo.py."

with open(OUT, "w") as f:
    json.dump(out, f, indent=2)
    f.write("\n")

print(f"wrote {OUT}: {len(trimmed_paths)} paths, {len(trimmed_defs)} definitions")
