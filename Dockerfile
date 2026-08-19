# Build context must be the parent directory containing both this repo and
# a Shotgun checkout as siblings, e.g. from that parent:
#   docker build -f anvil/Dockerfile -t anvil .
FROM rust:1-slim AS build
WORKDIR /src
COPY shotgun/ ./
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /anvil
COPY --from=build /src/target/release/shotgun /usr/local/bin/shotgun
COPY anvil/mappings.toml ./mappings.toml
COPY anvil/specs/github-rest-api.json anvil/specs/forgejo-api.json ./specs/

ENV ANVIL_LISTEN=0.0.0.0:3000
EXPOSE 3000

ENTRYPOINT ["/bin/sh", "-c", "exec shotgun serve --mappings mappings.toml --target-url \"$FORGEJO_URL\" --listen \"${ANVIL_LISTEN:-0.0.0.0:3000}\" --log-level \"${ANVIL_LOG_LEVEL:-info}\""]
